"""
Парсер td-marman.ru — каталог «Мастики ТЕХНОНИКОЛЬ».

Сайт — интернет-магазин стройматериалов на 1С-Битрикс + шаблон Aspro.
robots.txt разрешает парсинг каталога.

Особенность: карточки размечены Schema.org microdata — это самый надёжный
источник данных, не зависящий от косметических правок вёрстки:
    - <meta itemprop="name" content="...">               — название
    - <meta itemprop="price" content="844.8">            — цена (число!)
    - <link itemprop="url" href="/product/...">          — ссылка
    - <link itemprop="availability" href="...InStock">   — наличие
    - <meta itemprop="priceCurrency" content="RUB">      — валюта

Мы используем именно microdata, а CSS-селекторы — только как резерв.

Фильтр по бренду: сайт уже отдаёт только Технониколь (страница каталога
ТН), но из практики в списке присутствуют суб-бренды AquaMast / Империал /
Isobox. Их исключаем — по аналогии с parser_tophouse, чтобы отчёт был
консистентным.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional
from urllib.parse import urljoin

from parsers.base_parser import BaseParser

logger = logging.getLogger(__name__)

# --- Селекторы ---

# Карточка товара в списке
CARD_SELECTORS = [
    'div.catalog-block__item[id^="bx_"]',   # основной
    'div.catalog-block__item',
    'div.catalog-block__wrapper',
]

# Название (резерв — сначала пробуем meta[itemprop="name"])
NAME_SELECTORS = [
    'meta[itemprop="name"]',
    'div.catalog-block__info-title a span',
    'a.switcher-title span',
]

# Цена (сначала meta[itemprop="price"], потом span)
PRICE_SELECTORS = [
    'meta[itemprop="price"]',
    'span.price__new-val',
    'div.price__new span',
]

# Ссылка
LINK_SELECTORS = [
    'link[itemprop="url"]',
    'a.image-list__link',
    'div.catalog-block__info-title a',
    'a.switcher-title',
]

# Наличие
AVAILABILITY_LINK_SELECTOR = 'link[itemprop="availability"]'

# Суб-бренды TechnoNICOL, которые исключаем из отчёта
EXCLUDE_SUBBRANDS_REGEX = re.compile(
    r"aquamast|аквамаст|imperial|империал|isobox|изобокс",
    flags=re.IGNORECASE,
)


class ParserTdMarman(BaseParser):
    """Парсер td-marman.ru."""

    site_name = "td-marman.ru"
    base_url = "https://td-marman.ru"

    # Каталог «Мастики ТЕХНОНИКОЛЬ» + попытки показать все товары сразу.
    SEARCH_URLS = [
        # 1) Попробовать SHOWALL — Битрикс часто поддерживает этот параметр
        "https://td-marman.ru/catalog/gidroizolyatsiya/mastiki-i-praymery/mastiki/tekhnonikol/?SHOWALL_1=1",
        # 2) Первая страница каталога
        "https://td-marman.ru/catalog/gidroizolyatsiya/mastiki-i-praymery/mastiki/tekhnonikol/",
        # 3) Вторая страница — на случай, если SHOWALL не сработал (33 товара, ~20 на страницу)
        "https://td-marman.ru/catalog/gidroizolyatsiya/mastiki-i-praymery/mastiki/tekhnonikol/?PAGEN_1=2",
    ]

    MAX_CARDS_PER_URL = 50  # с запасом

    # ---------- Основной метод ----------

    def parse(self) -> list[dict[str, Any]]:
        all_records: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        # 1. Прогрев
        self._warmup()

        # 2. Проходим по всем URL
        for candidate_url in self.SEARCH_URLS:
            logger.info("[%s] Пробуем URL: %s", self.site_name, candidate_url)

            if not self._safe_goto(candidate_url):
                continue

            card_selector = self._wait_for_any_selector(
                CARD_SELECTORS, timeout_ms=15_000
            )
            if not card_selector:
                logger.warning(
                    "[%s] На %s карточки не найдены, пропускаем URL",
                    self.site_name, candidate_url,
                )
                continue

            self._smooth_scroll()

            try:
                cards = self._page.query_selector_all(card_selector)
            except Exception as e:
                logger.error("[%s] Ошибка при получении карточек: %s",
                             self.site_name, e)
                continue

            logger.info("[%s] На %s найдено карточек: %d",
                        self.site_name, candidate_url, len(cards))

            for idx, card in enumerate(cards[: self.MAX_CARDS_PER_URL], start=1):
                record = self._parse_card(card, idx)
                if not record:
                    continue
                # Дедупликация по URL товара
                if record["url"] in seen_urls:
                    continue
                seen_urls.add(record["url"])
                all_records.append(record)

        logger.info("[%s] ИТОГО: %d уникальных позиций Технониколь",
                    self.site_name, len(all_records))
        return all_records

    # ---------- Вспомогательные методы ----------

    def _wait_for_any_selector(self, selectors: list[str], timeout_ms: int) -> Optional[str]:
        per_selector = max(1000, timeout_ms // len(selectors))
        for sel in selectors:
            try:
                self._page.wait_for_selector(sel, timeout=per_selector)
                return sel
            except Exception:
                continue
        try:
            self._page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except Exception:
            pass
        for sel in selectors:
            if self._page.query_selector(sel):
                return sel
        return None

    def _smooth_scroll(self) -> None:
        try:
            for step in (0.25, 0.5, 0.75, 1.0):
                self._page.evaluate(
                    f"window.scrollTo(0, document.body.scrollHeight * {step});"
                )
                self._page.wait_for_timeout(400)
            self._page.evaluate("window.scrollTo(0, 0);")
            self._page.wait_for_timeout(300)
        except Exception as e:
            logger.debug("[%s] Ошибка при прокрутке: %s", self.site_name, e)

    def _parse_card(self, card, idx: int) -> Optional[dict[str, Any]]:
        """Извлечь запись из одной карточки."""
        name = self._extract_name(card)
        if not name:
            return None

        url = self._extract_url(card)
        if not url:
            return None

        # Фильтр по бренду: имя ИЛИ URL должны содержать Технониколь/ТН,
        # И НЕ быть суб-брендом AquaMast/Империал/Isobox.
        if EXCLUDE_SUBBRANDS_REGEX.search(name):
            return None

        # Проверка бренда — по названию или по URL
        is_tn = bool(
            re.search(r"техно[\s\-]?нико?л?ь|\bтн\s*№?\s*\d|техномаст|мгтн|эврика|фиксер|вишера|пламя\s*стоп",
                      name, flags=re.IGNORECASE)
            or re.search(r"tehnonikol|tekhnonikol|technonikol|-tn-?\d",
                         url, flags=re.IGNORECASE)
        )
        if not is_tn:
            return None

        price = self._extract_price(card)
        availability = self._extract_availability(card)
        unit, package_size = self._extract_unit_and_package(name)

        return self._build_record(
            product_name=name,
            price=price,
            unit=unit,
            package_size=package_size,
            availability=availability,
            url=url,
        )

    def _extract_name(self, card) -> Optional[str]:
        """Название: сначала meta[itemprop=name] (content), потом текст ссылки."""
        # 1. Schema.org
        meta = card.query_selector('meta[itemprop="name"]')
        if meta:
            content = (meta.get_attribute("content") or "").strip()
            if content:
                return content

        # 2. Текст ссылки
        for sel in NAME_SELECTORS[1:]:
            el = card.query_selector(sel)
            if el:
                text = (el.inner_text() or "").strip()
                if text:
                    return text
        return None

    def _extract_price(self, card) -> Optional[float]:
        """Цена: сначала meta[itemprop=price] (content — чистое число!)."""
        meta = card.query_selector('meta[itemprop="price"]')
        if meta:
            content = (meta.get_attribute("content") or "").strip()
            if content:
                parsed = self._parse_price_string(content)
                if parsed is not None:
                    return parsed

        for sel in PRICE_SELECTORS[1:]:
            el = card.query_selector(sel)
            if not el:
                continue
            parsed = self._parse_price_string(el.inner_text() or "")
            if parsed is not None:
                return parsed
        return None

    @staticmethod
    def _parse_price_string(raw: str) -> Optional[float]:
        """Универсальный парсинг строки с ценой."""
        if not raw:
            return None
        m = re.search(r"\d[\d\s\u00a0\u202f\u2007\u2009\u200a\u200b.,]*\d|\d", raw)
        if not m:
            return None
        num_str = m.group(0)
        num_str = re.sub(r"[\s\u00a0\u202f\u2007\u2009\u200a\u200b]+", "", num_str)
        if "," in num_str and "." in num_str:
            if num_str.rfind(",") > num_str.rfind("."):
                num_str = num_str.replace(".", "").replace(",", ".")
            else:
                num_str = num_str.replace(",", "")
        elif "," in num_str:
            num_str = num_str.replace(",", ".")
        try:
            return float(num_str)
        except ValueError:
            return None

    def _extract_url(self, card) -> Optional[str]:
        """URL: сначала link[itemprop=url] (href), потом обычные ссылки."""
        # 1. Schema.org
        link = card.query_selector('link[itemprop="url"]')
        if link:
            href = (link.get_attribute("href") or "").strip()
            if href:
                return urljoin(self.base_url, href).split("#", 1)[0]

        # 2. Обычные <a>
        for sel in LINK_SELECTORS[1:]:
            el = card.query_selector(sel)
            if not el:
                continue
            href = el.get_attribute("href")
            if href:
                return urljoin(self.base_url, href).split("#", 1)[0]
        return None

    def _extract_availability(self, card) -> Optional[str]:
        """
        Наличие: сначала link[itemprop=availability] (schema.org),
        потом — по ключевым словам в тексте карточки.
        """
        link = card.query_selector(AVAILABILITY_LINK_SELECTOR)
        if link:
            href = (link.get_attribute("href") or "").strip().lower()
            mapping = {
                "instock": "в наличии",
                "outofstock": "нет в наличии",
                "preorder": "предзаказ",
                "backorder": "под заказ",
                "soldout": "распродано",
                "discontinued": "снят с производства",
                "limitedavailability": "ограниченное наличие",
                "onlineonly": "только онлайн",
            }
            for key, val in mapping.items():
                if key in href:
                    return val

        # Резерв — по тексту
        try:
            text = (card.inner_text() or "").lower()
        except Exception:
            return None
        for hint in ("в наличии", "на складе", "под заказ", "нет в наличии",
                     "ожидается", "закончился", "предзаказ"):
            if hint in text:
                return hint
        return None

    @staticmethod
    def _extract_unit_and_package(name: str) -> tuple[Optional[str], Optional[str]]:
        """
        Единица и фасовка из названия.
        Вырезаем «№N» (артикульный номер продукта №21, №24, №27, №71)
        и берём ПОСЛЕДНЕЕ совпадение «<число><единица>» — фасовка в конце.
        """
        unit = None
        package_size = None

        cleaned_name = re.sub(r"№\s*\d+", " ", name)
        cleaned_name = re.sub(r"no\.?\s*\d+", " ", cleaned_name, flags=re.IGNORECASE)

        matches = re.findall(
            r"(\d+(?:[.,]\d+)?)\s*(кг|г|л|мл|шт|литр(?:ов|а)?|штук(?:а|и)?)\b",
            cleaned_name, flags=re.IGNORECASE,
        )
        if not matches:
            return None, None

        number_raw, raw_unit = matches[-1]
        number = number_raw.replace(",", ".")
        raw_unit_low = raw_unit.lower()
        if raw_unit_low.startswith("литр"):
            unit = "л"
        elif raw_unit_low.startswith("штук"):
            unit = "шт"
        else:
            unit = raw_unit_low
        package_size = f"{number} {unit}"

        return unit, package_size