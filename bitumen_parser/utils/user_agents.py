"""
Пул реалистичных User-Agent браузера Chrome.

ВАЖНО: список ограничен Windows-платформой, потому что весь наш парсер
запускается на Windows (Playwright Chromium на Windows). Если UA будет
говорить «я macOS Chrome», а TLS-отпечаток и JS-фичи будут соответствовать
Windows — это триггер для антибот-систем. Поэтому — только Windows-UA.

Если в будущем парсер будет запускаться на Linux/macOS — расширьте
список соответствующими UA и фильтруйте пул по платформе.
"""

import random

# Реальные UA-строки Chrome на Windows 10/11.
# Версии разные, чтобы ротация была заметной.
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",

    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",

    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",

    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",

    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
]


def get_random_user_agent() -> str:
    """Вернуть случайный User-Agent из пула."""
    return random.choice(USER_AGENTS)