"""
Базовый класс Playwright-парсера.

Все конкретные парсеры (ksk24, tophouse, stroy-podskazka) наследуются
от BaseParser и реализуют только метод parse(), возвращающий список
словарей-записей о товарах.

Базовая логика:
    - запуск/остановка Playwright Chromium в headless-режиме;
    - ротация User-Agent на каждый браузерный контекст (Windows-only);
    - проверка robots.txt перед первым запросом;
    - retry с экспоненциальной задержкой при сетевых ошибках;
    - задержка между запросами не менее MIN_DELAY_SEC;
    - детект капчи/антибот-блокировки без попыток обхода;
    - метод прогрева _warmup() — короткий визит на главную перед поиском;
    - единый формат записи о товаре (см. _build_record).
"""

from __future__ import annotations

import logging
import random
import time
from datetime import datetime, timezone
from typing import Any, Optional

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from utils.robots_checker import check_site_or_skip
from utils.user_agents import get_random_user_agent

logger = logging.getLogger(__name__)


class BaseParser:
    """
    Базовый класс парсера. Наследники переопределяют:
        - site_name:   человекочитаемое имя сайта (для поля 'source');
        - base_url:    корневой URL сайта;
        - SEARCH_URLS: список URL страниц поиска/каталога (пробуются по очереди);
        - parse():     метод, возвращающий list[dict] записей о товарах.
    """

    # --- Настройки по умолчанию (можно переопределять в наследниках) ---
    site_name: str = "unknown"
    base_url: str = ""

    # Задержка между запросами (сек). Минимум 2–3 секунды.
    MIN_DELAY_SEC: float = 2.5
    MAX_DELAY_SEC: float = 4.5

    # Таймауты Playwright (мс)
    NAV_TIMEOUT_MS: int = 30_000
    SELECTOR_TIMEOUT_MS: int = 15_000

    # Retry при сетевых ошибках
    MAX_RETRIES: int = 3
    RETRY_BACKOFF_BASE: float = 3.0  # секунды: 3, 6, 12...

    # Признаки антибот-блокировки: если такие строки встретятся в тексте
    # страницы — считаем, что нас заблокировали, и НЕ пытаемся обходить.
    ANTIBOT_MARKERS = [
        "проверка браузера",
        "проверьте, что вы не робот",
        "проверьте что вы не робот",
        "checking your browser",
        "cf-challenge",
        "cloudflare",
        "captcha",
        "recaptcha",
        "доступ ограничен",
        "разверните картинку",   # rotate-captcha vseinstrumenti
    ]

    def __init__(self) -> None:
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._last_request_ts: float = 0.0
        # User-Agent текущего контекста — храним явно, чтобы не лазить
        # в приватные поля Playwright (в новых версиях они недоступны).
        self._current_user_agent: str = ""

    # ---------- Контекстный менеджер ----------

    def __enter__(self) -> "BaseParser":
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=True,
            args=[
                # Отключаем часть «шумных» фич, которые не нужны в headless
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        # Запоминаем выбранный UA в явной переменной
        self._current_user_agent = get_random_user_agent()

        # Новый контекст = свежий User-Agent + реалистичная локаль и viewport
        self._context = self._browser.new_context(
            user_agent=self._current_user_agent,
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            viewport={"width": 1366, "height": 768},
            extra_http_headers={
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )
        self._context.set_default_timeout(self.SELECTOR_TIMEOUT_MS)
        self._page = self._context.new_page()
        logger.info("[%s] Браузер запущен, UA=%s",
                    self.site_name, self._current_user_agent)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
        finally:
            if self._playwright:
                self._playwright.stop()
        logger.info("[%s] Браузер закрыт", self.site_name)

    # ---------- Утилиты ----------

    def _sleep_between_requests(self) -> None:
        """
        Пауза между двумя соседними запросами. Не менее MIN_DELAY_SEC секунд
        с момента прошлого запроса + случайный джиттер.
        """
        elapsed = time.time() - self._last_request_ts
        target_delay = random.uniform(self.MIN_DELAY_SEC, self.MAX_DELAY_SEC)
        if elapsed < target_delay:
            time.sleep(target_delay - elapsed)
        self._last_request_ts = time.time()

    def _is_antibot_page(self, page: Page) -> bool:
        """Проверить, не отдали ли нам страницу-заглушку антибота/капчи."""
        try:
            text = (page.inner_text("body", timeout=5_000) or "")[:3000].lower()
        except Exception:
            return False
        return any(marker in text for marker in self.ANTIBOT_MARKERS)

    def _warmup(self) -> None:
        """
        «Прогрев» сессии: короткий визит на главную страницу сайта перед
        переходом к поиску/каталогу. Имитирует обычное поведение
        пользователя (открыл сайт → осмотрелся → пошёл в поиск).

        Ошибки прогрева НЕ считаются фатальными — если что-то не получилось,
        просто пишем в лог и идём дальше.
        """
        if not self.base_url:
            return
        try:
            logger.info("[%s] Прогрев: открываем %s", self.site_name, self.base_url)
            self._sleep_between_requests()
            self._page.goto(self.base_url, wait_until="domcontentloaded",
                            timeout=self.NAV_TIMEOUT_MS)
            self._page.wait_for_timeout(random.randint(1000, 1800))
            self._page.evaluate(
                "window.scrollTo(0, document.body.scrollHeight * 0.4);"
            )
            self._page.wait_for_timeout(random.randint(600, 1200))

            if self._is_antibot_page(self._page):
                logger.warning(
                    "[%s] На главной странице обнаружены признаки антибота. "
                    "Продолжаем без прогрева — вероятен пропуск сайта.",
                    self.site_name,
                )
        except Exception as e:
            logger.warning("[%s] Прогрев не удался (не критично): %s",
                           self.site_name, e)

    def _safe_goto(self, url: str) -> bool:
        """
        Открыть URL с retry. Возвращает True при успехе, False — если
        после MAX_RETRIES всё ещё не удалось.
        """
        # Перед запросом — проверяем robots.txt именно для этого URL
        if not check_site_or_skip(url, self.site_name):
            return False

        for attempt in range(1, self.MAX_RETRIES + 1):
            self._sleep_between_requests()
            try:
                logger.info("[%s] GET %s (попытка %d/%d)",
                            self.site_name, url, attempt, self.MAX_RETRIES)
                self._page.goto(url, wait_until="domcontentloaded",
                                timeout=self.NAV_TIMEOUT_MS)

                self._page.wait_for_selector("body", timeout=self.SELECTOR_TIMEOUT_MS)

                if self._is_antibot_page(self._page):
                    logger.error(
                        "[%s] Обнаружена антибот-защита (капча/challenge). "
                        "Парсинг сайта пропускается — обход не выполняется.",
                        self.site_name,
                    )
                    return False

                return True

            except PlaywrightTimeoutError as e:
                logger.warning("[%s] Таймаут на попытке %d: %s",
                               self.site_name, attempt, e)
            except Exception as e:
                logger.warning("[%s] Ошибка на попытке %d: %s",
                               self.site_name, attempt, e)

            if attempt < self.MAX_RETRIES:
                backoff = self.RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                logger.info("[%s] Ждём %.1f сек перед повтором...",
                            self.site_name, backoff)
                time.sleep(backoff)

        logger.error("[%s] Не удалось загрузить %s после %d попыток",
                     self.site_name, url, self.MAX_RETRIES)
        return False

    def _build_record(
            self,
            product_name: str,
            price: Optional[float],
            unit: Optional[str],
            package_size: Optional[str],
            availability: Optional[str],
            url: str,
    ) -> dict[str, Any]:
        """Единый формат записи о товаре."""
        return {
            "product_name": product_name.strip(),
            "price": price,
            "unit": unit,
            "package_size": package_size,
            "availability": availability,
            "url": url,
            "source": self.site_name,
            "scrape_timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

    # ---------- Интерфейс наследника ----------

    def parse(self) -> list[dict[str, Any]]:
        raise NotImplementedError(
            f"{self.__class__.__name__}.parse() должен быть реализован"
        )