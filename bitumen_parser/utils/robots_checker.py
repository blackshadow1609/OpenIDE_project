"""
Проверка robots.txt перед парсингом.

Идея: перед запуском парсера конкретного сайта убеждаемся, что
запрашиваемый путь разрешён для нашего User-Agent. Если robots.txt
недоступен — считаем, что «не запрещено» (мягкая политика), но логируем.

Важно: этот модуль НЕ занимается обходом ограничений. Если путь
запрещён — вызывающий код обязан пропустить парсинг.
"""

import logging
from functools import lru_cache
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

logger = logging.getLogger(__name__)

# Таймаут на скачивание robots.txt (сек)
ROBOTS_TIMEOUT = 10

# User-Agent по умолчанию для проверки правил.
# Парсеры должны передавать сюда РЕАЛЬНЫЙ UA из user_agents.py,
# чтобы robots.txt проверялся для той же роли, под которой мы ходим.
# Дефолт "*" используется только как fallback при прямом вызове.
ROBOTS_USER_AGENT = "*"


def _is_allowed_uncached(url: str, user_agent: str) -> bool:
    """Некэшированная проверка robots.txt (внутренняя)."""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        logger.warning("Некорректный URL: %s", url)
        return False

    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    rp = RobotFileParser()
    try:
        # Скачиваем robots.txt вручную через requests,
        # чтобы контролировать таймаут и заголовки.
        # UA для скачивания совпадает с UA, под которым ходит парсер.
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


@lru_cache(maxsize=64)
def _is_allowed_cached(scheme: str, netloc: str, path: str, user_agent: str) -> bool:
    """
    Кэш по (схема, домен, путь, UA).
    Кэш живёт в течение процесса — на 50 URL это даёт 1 запрос robots.txt
    на сайт вместо 15. Сбрасывается автоматически при перезапуске.
    """
    return _is_allowed_uncached(f"{scheme}://{netloc}{path}", user_agent)


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
    return _is_allowed_cached(
        parsed.scheme, parsed.netloc, parsed.path or "/", user_agent
    )


def check_site_or_skip(url: str, site_name: str,
                       user_agent: str = ROBOTS_USER_AGENT) -> bool:
    """
    Обёртка для использования в парсерах: проверяет robots.txt
    и логирует результат в удобочитаемом виде.

    user_agent должен совпадать с тем, под которым реально ходит парсер —
    иначе правило сайта для конкретного UA может не сработать.

    Возвращает True, если можно парсить, False — если сайт нужно пропустить.
    """
    if is_allowed(url, user_agent=user_agent):
        logger.info("[%s] robots.txt разрешает парсинг %s", site_name, url)
        return True

    logger.error(
        "[%s] robots.txt ЗАПРЕЩАЕТ парсинг %s для UA=%s. Сайт будет пропущен. "
        "Замените его на альтернативный источник.",
        site_name, url, user_agent,
    )
    return False