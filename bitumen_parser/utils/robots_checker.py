"""
Проверка robots.txt перед парсингом.

Идея: перед запуском парсера конкретного сайта убеждаемся, что
запрашиваемый путь разрешён для нашего User-Agent. Если robots.txt
недоступен — считаем, что «не запрещено» (мягкая политика), но логируем.

Важно: этот модуль НЕ занимается обходом ограничений. Если путь
запрещён — вызывающий код обязан пропустить парсинг.
"""

import logging
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

logger = logging.getLogger(__name__)

# Таймаут на скачивание robots.txt (сек)
ROBOTS_TIMEOUT = 10

# User-Agent для проверки правил.
# Указываем "*" — правила для анонимных/неизвестных ботов.
# Если захотим представиться — можно указать, например,
# "BitumenPriceBot/1.0".
ROBOTS_USER_AGENT = "*"


def is_allowed(url: str, user_agent: str = ROBOTS_USER_AGENT) -> bool:
    """
    Проверить, разрешён ли доступ к url согласно robots.txt его домена.

    Возвращает:
        True  — доступ разрешён ИЛИ robots.txt недоступен (мягкая политика);
        False — доступ явно запрещён или robots.txt запрещает все пути.
    """
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        logger.warning("Некорректный URL: %s", url)
        return False

    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    rp = RobotFileParser()
    try:
        # Скачиваем robots.txt вручную через requests,
        # чтобы контролировать таймаут и заголовки.
        resp = requests.get(
            robots_url,
            timeout=ROBOTS_TIMEOUT,
            headers={"User-Agent": user_agent if user_agent != "*" else "Mozilla/5.0"},
        )
        if resp.status_code >= 400:
            # robots.txt отсутствует (404) — обычно это означает «не запрещено»
            logger.info("robots.txt недоступен (%s): %s", resp.status_code, robots_url)
            return True

        rp.parse(resp.text.splitlines())

    except requests.RequestException as e:
        # Сетевые проблемы — не блокируем парсер, но пишем в лог
        logger.warning("Не удалось скачать robots.txt %s: %s", robots_url, e)
        return True

    allowed = rp.can_fetch(user_agent, url)
    if not allowed:
        logger.warning("robots.txt запрещает доступ к %s для UA=%s", url, user_agent)
    return allowed


def check_site_or_skip(url: str, site_name: str) -> bool:
    """
    Обёртка для использования в парсерах: проверяет robots.txt
    и логирует результат в удобочитаемом виде.

    Возвращает True, если можно парсить, False — если сайт нужно пропустить.
    """
    if is_allowed(url):
        logger.info("[%s] robots.txt разрешает парсинг %s", site_name, url)
        return True

    logger.error(
        "[%s] robots.txt ЗАПРЕЩАЕТ парсинг %s. Сайт будет пропущен. "
        "Замените его на альтернативный источник.",
        site_name, url,
    )
    return False