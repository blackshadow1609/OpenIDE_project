"""
Парсер ksk24.ru — поиск «битумная мастика Технониколь».

Сайт — интернет-магазин стройматериалов. robots.txt разрешает парсинг.
Поиск работает через обычный ?q=.

Стратегия:
    1. Прогрев — открываем главную страницу.
    2. Проходим ПО ВСЕМ URL из SEARCH_URLS (не останавливаемся на первом):
       это даёт больше карточек, чем один запрос.
    3. Из каждой страницы собираем позиции.
    4. Дедуплицируем по URL товара.
    5. Фильтруем только позиции Технониколь — по названию ИЛИ по URL.
       У ksk24 бренд в названии часто сокращён до «ТН №N», поэтому одной
       проверки названия недостаточно.
    6. Возвращаем список записей.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional
from urllib.parse import quote_plus, urljoin

from parsers.base_parser import BaseParser

logger = logging.getLogger(__name__)

# --- Селекторы: реальные для ksk24.ru + резерв на случай смены вёрстки ---

CARD_SELECTORS = [
    'li.products__item',
    'li[data-product-id]',
    'div[class*="product-card"]',
    'article[class*="product"]',
]

NAME_SELECTORS = [
    'div.products__name > a > span',
    'div.products__name a',
    '[itemprop="name"]',
    'a[class*="name"]',
]

PRICE_SELECTORS = [
    'span.products__price',
    'div.products__col-3 span[class*="price"]',
    '[itemprop="price"]',
    'span[class*="price"]',
    'div[class*="price"]',
]

LINK_SELECTORS = [
    'a.products__link',
    'div.products__name a',
    'a[itemprop="url"]',
    'a[href*="/catalog/"]',
]

AVAILABILITY_HINTS = [
    "в наличии", "на складе", "под заказ", "нет в наличии",
    "ожидается", "закончился", "предзаказ", "уточняйте",
]

# --- Проверка бренда Технониколь -----------------------------------------
# Проверка по НАЗВАНИЮ. Покрываем:
#   - полное название: Технониколь / ТЕХНОНИКОЛЬ / ТехноНИКОЛЬ / Техно-НИКОЛЬ / TechnoNICOL
#   - аббревиатуру «ТН №N» (так ksk24 обозначает продукцию Технониколь)
#   - торговые марки Технониколь: Техномаст, Пламя Стоп, МГТН, Эврика, Фиксер, Вишера
BRAND_NAME_REGEX = re.compile(
    r"техно[\s\-]?нико?л?ь"
    r"|techno[\s\-]?nikol"
    r"|\bтн\s*№?\s*\d"
    r"|техномаст"
    r"|пламя\s*стоп"
    r"|мгтн"
    r"|эврика"
    r"|фиксер"
    r"|вишера",
    flags=re.IGNORECASE,
)

# Проверка по URL товара. В URL ksk24 продукция Технониколь встречается как:
#   /mastika-tekhnonikol-...   — полный бренд
#   /...-tn-21-...             — аббревиатура
#   /...-tn-27-...
BRAND_URL_REGEX = re.compile(
    r"tehnonikol|tekhnonikol|technonikol|-tn-?\d|/tn-?\d",
    flags=re.IGNORECASE,
)


class ParserKsk24(BaseParser):
    """Парсер ksk24.ru."""

    site_name = "ksk24.ru"
    base_url = "https://ksk24.ru"

    # Список URL — проходим ВСЕ, результаты объединяем.
    # 1-й даёт точные совпадения «мастика технониколь», 2-й — широкий охват.
    SEARCH_URLS = [
        "https://ksk24.ru/search/?q=" + quote_plus("мастика технониколь"),
        "https://ksk24.ru/search/?q=" + quote_plus("мастика"),
        ]

    # Лимит карточек на КАЖДУЮ страницу (для демо-режима).
    MAX_CARDS_PER_URL = 30

    # ---------- Основной метод ----------

    def parse(self) -> list[dict[str, Any]]:
        """Открыть страницы поиска и собрать позиции по всем URL."""
        all_records: list[dict[str, Any]] = []
        seen_urls: set[str] = set()  # дедупликация по ссылке товара

        # 1. Прогрев — короткий визит на главную
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

            # 3. Прокрутка — на случай ленивой подгрузки
            self._smooth_scroll()

            # 4. Собираем карточки
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
                # Дедупликация: если такой URL уже видели — пропускаем
                if record["url"] in seen_urls:
                    continue
                seen_urls.add(record["url"])
                all_records.append(record)

        logger.info(
            "[%s] ИТОГО: %d уникальных позиций Технониколь",
            self.site_name, len(all_records),
        )
        return all_records

    # ---------- Вспомогательные методы ----------

    def _wait_for_any_selector(self, selectors: list[str], timeout_ms: int) -> Optional[str]:
        """Ждём появления любого селектора, возвращаем первый сработавший."""
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
        """Плавная прокрутка — триггерит ленивую подгрузку."""
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

        # URL нужен и для фильтра бренда, и для итоговой записи
        url = self._extract_url(card)
        if not url:
            return None

        # Фильтр бренда: название ИЛИ URL содержит признаки Технониколь.
        # Это позволяет поймать «ТН №21», «Техномаст» и т.п.
        if not (BRAND_NAME_REGEX.search(name) or BRAND_URL_REGEX.search(url)):
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
        for sel in NAME_SELECTORS:
            el = card.query_selector(sel)
            if el:
                text = (el.inner_text() or "").strip()
                if text:
                    return text
                title = (el.get_attribute("title") or "").strip()
                if title:
                    return title
        return None

    def _extract_price(self, card) -> Optional[float]:
        """
        Извлечь цену из карточки ksk24.
        Основной путь — span.products__price. Дополнительно пробуем
        резервные селекторы и сбор текста вложенных элементов.
        """
        for sel in PRICE_SELECTORS:
            try:
                el = card.query_selector(sel)
            except Exception:
                continue
            if not el:
                continue

            # 1) itemprop=price может хранить число в content
            content = el.get_attribute("content")
            if content:
                parsed = self._parse_price_string(content)
                if parsed is not None:
                    return parsed

            # 2) inner_text (главный путь)
            parsed = self._parse_price_string(el.inner_text() or "")
            if parsed is not None:
                return parsed

            # 3) запасной путь — текстовые узлы всех вложенных элементов
            try:
                text_all = el.evaluate(
                    "node => Array.from(node.querySelectorAll('*'))"
                    ".map(n => n.textContent).join(' ')"
                )
                parsed = self._parse_price_string(text_all or "")
                if parsed is not None:
                    return parsed
            except Exception:
                pass

        return None

    @staticmethod
    def _parse_price_string(raw: str) -> Optional[float]:
        """
        Универсальный парсинг строки с ценой в float.

        Идея: НЕ вычищаем мусор, а сразу ищем первую числовую подстроку.
        Это устойчивее к любым посторонним символам — точкам от «руб.»,
        запятым от формата чисел, слешам от «/ шт.» и т.д.

        Схема:
            1. Ищем первое вхождение «цифра ... цифра» с разделителями
               (пробелы любых Unicode-видов, точка, запятая).
            2. Убираем все пробельные символы.
            3. Приводим десятичный разделитель к точке.
            4. Парсим в float.
        """
        if not raw:
            return None

        # 1. Находим первую подстроку-число.
        #    Жадный матч: начинается с цифры, заканчивается цифрой,
        #    внутри — цифры и разделители.
        m = re.search(
            r"\d[\d\s\u00a0\u202f\u2007\u2009\u200a\u200b.,]*\d|\d",
            raw,
        )
        if not m:
            return None
        num_str = m.group(0)

        # 2. Убираем все виды пробелов
        num_str = re.sub(
            r"[\s\u00a0\u202f\u2007\u2009\u200a\u200b]+", "", num_str
        )

        # 3. Определяем десятичный разделитель.
        #    Если оба разделителя есть — тот, который правее, считаем
        #    десятичным, а левый — разделителем тысяч.
        if "," in num_str and "." in num_str:
            if num_str.rfind(",") > num_str.rfind("."):
                # «1.234,56» → запятая десятичная
                num_str = num_str.replace(".", "").replace(",", ".")
            else:
                # «1,234.56» → точка десятичная
                num_str = num_str.replace(",", "")
        elif "," in num_str:
            num_str = num_str.replace(",", ".")

        # 4. Финальный парсинг
        try:
            return float(num_str)
        except ValueError:
            return None

    def _extract_url(self, card) -> Optional[str]:
        for sel in LINK_SELECTORS:
            el = card.query_selector(sel)
            if not el:
                continue
            href = el.get_attribute("href")
            if href:
                return urljoin(self.base_url, href).split("#", 1)[0]
        return None

    def _extract_availability(self, card) -> Optional[str]:
        """Наличие: сначала ищем в .product-info__item--availability, потом по ключам."""
        try:
            el = card.query_selector('li.product-info__item--availability span')
            if el:
                text = (el.inner_text() or "").strip()
                if text:
                    text = re.sub(r"^\s*наличие\s*:\s*", "", text, flags=re.IGNORECASE)
                    if text:
                        return text
        except Exception:
            pass

        try:
            text = (card.inner_text() or "").lower()
        except Exception:
            return None
        for hint in AVAILABILITY_HINTS:
            if hint in text:
                return hint
        return None

    @staticmethod
    def _extract_unit_and_package(name: str) -> tuple[Optional[str], Optional[str]]:
        """Вытащить единицу измерения и фасовку из названия."""
        unit = None
        package_size = None
        m = re.search(
            r"(\d+[.,]?\d*)\s*(кг|г|л|мл|шт|литр(?:ов|а)?|штук(?:а|и)?)",
            name, flags=re.IGNORECASE,
        )
        if m:
            number = m.group(1).replace(",", ".")
            raw_unit = m.group(2).lower()
            if raw_unit.startswith("литр"):
                unit = "л"
            elif raw_unit.startswith("штук"):
                unit = "шт"
            else:
                unit = raw_unit
            package_size = f"{number} {unit}"
        return unit, package_size