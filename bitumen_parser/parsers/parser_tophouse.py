"""
Парсер tophouse.ru — поиск «мастика Технониколь».

Сайт — интернет-магазин стройматериалов. robots.txt разрешает парсинг.
Поиск работает через обычный ?q=, нечёткий (находит товары даже с опечатками).

Реальная вёрстка карточки (по данным разведки):
    <div class="product product-list__container-item">
        <a href="/price/..." class="product__name" title="Название товара">
            <span class="product__name-content">Название товара</span>
        </a>
        <div class="product__characteristics">
            <div class="product__characteristic">Бренд: ТехноНиколь</div>
            <div class="product__characteristic">Страна: Россия</div>
        </div>
        <div class="product__measures">
            <div class="product__measure">шт.</div>
        </div>
        <div class="product__prices">
            <div class="product__price">10 714.80 ₽</div>
        </div>
    </div>

Фильтр по бренду — прямой поиск «Бренд: ТехноНиколь» в блоке характеристик.

Стратегия:
    1. Прогрев — открываем главную.
    2. Проходим по SEARCH_URLS.
    3. Ждём появления карточек (div.product).
    4. Фильтруем по бренду — через поле «Бренд:».
    5. Извлекаем название, цену, ссылку, единицу.
    6. Возвращаем список записей.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional
from urllib.parse import quote_plus, urljoin

from parsers.base_parser import BaseParser

logger = logging.getLogger(__name__)

# --- Реальные селекторы tophouse.ru ---

CARD_SELECTORS = [
    'div.product.product-list__container-item',
    'div.product[data-v-d54572dd]',
    'div.product',
]

NAME_SELECTORS = [
    'a.product__name',
    'a.product__name[href]',
]

PRICE_SELECTORS = [
    'div.product__price',
]

LINK_SELECTORS = [
    'a.product__name[href]',
    'a.image-link[href]',
]

# Поле «Бренд: X» внутри блока характеристик
BRAND_CHAR_SELECTOR = 'div.product__characteristic'

AVAILABILITY_HINTS = [
    "в наличии", "на складе", "под заказ", "нет в наличии",
    "ожидается", "закончился", "предзаказ", "по запросу",
]


class ParserTophouse(BaseParser):
    """Парсер tophouse.ru."""

    site_name = "tophouse.ru"
    base_url = "https://www.tophouse.ru"

    # Поиск работает через обычный ?q=. Нечёткий — находит с опечатками.
    SEARCH_URLS = [
        "https://www.tophouse.ru/search/?q=" + quote_plus("Мастика техниколь"),
        "https://www.tophouse.ru/search/?q=" + quote_plus("Мастика технониколь"),
        "https://www.tophouse.ru/search/?q=" + quote_plus("мастика"),
        ]

    MAX_CARDS_PER_URL = 40  # на странице «Найдено 32» — с запасом

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
        # --- Фильтр по бренду: ищем «Бренд: ТехноНиколь» среди характеристик ---
        if not self._has_technonikol_brand(card):
            return None

        name = self._extract_name(card)
        if not name:
            return None

        url = self._extract_url(card)
        if not url:
            return None

        price = self._extract_price(card)
        availability = self._extract_availability(card)
        unit, package_size = self._extract_unit_and_package(name)

        # Единицу измерения НЕ переопределяем из блока .product__measure:
        # там у tophouse всегда «шт.» (это единица продажи), а не физическая
        # фасовка товара (кг/л). Приоритет — тому, что написано в названии.
        if not unit:
            # Если в названии единицы не было — берём хотя бы из блока мер
            unit_from_block = self._extract_unit_from_block(card)
            if unit_from_block:
                unit = unit_from_block

        return self._build_record(
            product_name=name,
            price=price,
            unit=unit,
            package_size=package_size,
            availability=availability,
            url=url,
        )

    def _has_technonikol_brand(self, card) -> bool:
        """
        Проверить, что в блоке характеристик карточки есть строка
        «Бренд: ТехноНиколь». Это точнее, чем регулярка по всему тексту.
        """
        try:
            chars = card.query_selector_all(BRAND_CHAR_SELECTOR)
            for ch in chars:
                text = (ch.inner_text() or "").strip()
                # «Бренд: ТехноНиколь» или «Бренд: ТЕХНОНИКОЛЬ» и т.п.
                if re.match(r"^Бренд\s*:\s*техно\s*н?и?коль", text, flags=re.IGNORECASE):
                    return True
        except Exception:
            pass
        return False

    def _extract_name(self, card) -> Optional[str]:
        """Название берём из a.product__name[title] — там полный текст без обрезки."""
        for sel in NAME_SELECTORS:
            el = card.query_selector(sel)
            if el:
                # title полнее, чем inner_text (внутренний span может быть обрезан CSS)
                title = (el.get_attribute("title") or "").strip()
                if title:
                    return title
                text = (el.inner_text() or "").strip()
                if text:
                    return text
        return None

    def _extract_price(self, card) -> Optional[float]:
        """
        Цена: либо число (например, «10 714.80 ₽»), либо текст «По запросу».
        Если «По запросу» — возвращаем None, это нормально для tophouse.
        """
        for sel in PRICE_SELECTORS:
            try:
                el = card.query_selector(sel)
            except Exception:
                continue
            if not el:
                continue
            text = (el.inner_text() or "").strip()
            if not text or "по запросу" in text.lower():
                return None
            parsed = self._parse_price_string(text)
            if parsed is not None:
                return parsed
        return None

    @staticmethod
    def _parse_price_string(raw: str) -> Optional[float]:
        """Универсальный парсинг строки с ценой."""
        if not raw:
            return None
        m = re.search(
            r"\d[\d\s\u00a0\u202f\u2007\u2009\u200a\u200b.,]*\d|\d",
            raw,
        )
        if not m:
            return None
        num_str = m.group(0)
        num_str = re.sub(
            r"[\s\u00a0\u202f\u2007\u2009\u200a\u200b]+", "", num_str
        )
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
        for sel in LINK_SELECTORS:
            el = card.query_selector(sel)
            if not el:
                continue
            href = el.get_attribute("href")
            if href:
                return urljoin(self.base_url, href).split("#", 1)[0]
        return None

    def _extract_availability(self, card) -> Optional[str]:
        """
        Наличие: смотрим бейджи «НА СКЛАДЕ», а также «По запросу» в цене.
        """
        try:
            text = (card.inner_text() or "").lower()
        except Exception:
            return None
        # Если в тексте есть «по запросу» — это тоже про наличие/цену
        if "по запросу" in text:
            return "по запросу"
        for hint in AVAILABILITY_HINTS:
            if hint in text:
                return hint
        return None

    def _extract_unit_from_block(self, card) -> Optional[str]:
        """Единица измерения из блока .product__measure (шт., рулон, упак. и т.п.)."""
        try:
            el = card.query_selector('div.product__measure')
            if el:
                text = (el.inner_text() or "").strip()
                if text:
                    return text
        except Exception:
            pass
        return None

    @staticmethod
    def _extract_unit_and_package(name: str) -> tuple[Optional[str], Optional[str]]:
        """
        Единица и фасовка из названия.

        Важно: игнорируем «№N» (артикульный номер продукта — №21, №24, №27),
        чтобы не спутать его с фасовкой. Ищем все совпадения «<число> <единица>»
        и берём ПОСЛЕДНЕЕ — в названиях типа «... ведро 22 кг» или «... 20кг»
        фасовка стоит в конце.
        """
        unit = None
        package_size = None

        # Защита от «№21», «№ 24», «N°57» — вырезаем артикульные номера
        cleaned_name = re.sub(r"№\s*\d+", " ", name)
        cleaned_name = re.sub(r"no\.?\s*\d+", " ", cleaned_name, flags=re.IGNORECASE)

        # Ищем все вхождения «<число><единица>»
        #   Единицы: кг, г, л, мл, шт, литр(ов), штук(а/и)
        #   Разделитель: «20 кг», «20кг», «20,6 л», «0,4 кг»
        matches = re.findall(
            r"(\d+(?:[.,]\d+)?)\s*(кг|г|л|мл|шт|литр(?:ов|а)?|штук(?:а|и)?)\b",
            cleaned_name, flags=re.IGNORECASE,
        )
        if not matches:
            return None, None

        # Берём последнее совпадение — фасовка обычно в конце названия
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