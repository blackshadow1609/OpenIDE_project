"""
Диагностика страницы ksk24.ru — что реально отдаёт сайт
по нашим URL поиска. Сохраняем HTML и скриншоты.
"""

from playwright.sync_api import sync_playwright
import time

URLS = [
    "https://ksk24.ru/search/?q=мастика",
    "https://ksk24.ru/search/?q=мастика+технониколь",
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(locale="ru-RU", timezone_id="Europe/Moscow")
    page = ctx.new_page()

    for i, url in enumerate(URLS, start=1):
        print(f"\n=== URL #{i}: {url} ===")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print("goto error:", e)
            continue

        # Ждём «тихую» сеть и рендер
        try:
            page.wait_for_load_state("networkidle", timeout=20000)
            print("networkidle OK")
        except Exception as e:
            print("networkidle timeout:", e)

        page.wait_for_timeout(5000)

        print("Текущий URL:", page.url)
        print("Заголовок:", page.title() or "(пусто)")

        # HTML — с retry (SPA может мигнуть)
        html = None
        for attempt in range(3):
            try:
                html = page.content()
                break
            except Exception as e:
                print(f"content() attempt {attempt+1} failed:", e)
                time.sleep(2)

        if html:
            fname = f"debug_ksk24_{i}.html"
            with open(fname, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"HTML сохранён: {fname}, длина = {len(html)}")
        else:
            print("HTML не удалось получить")

        try:
            page.screenshot(path=f"debug_ksk24_{i}.png", full_page=False)
            print(f"Скриншот: debug_ksk24_{i}.png")
        except Exception as e:
            print("screenshot error:", e)

        # Быстрый поиск характерных маркеров
        if html:
            for marker in [
                "product", "catalog-item", "itemtype", "Product",
                "Технониколь", "Техноникол", "мастика",
                "ничего не найдено", "не нашлось", "нет результатов",
                "captcha", "cloudflare",
            ]:
                if marker.lower() in html.lower():
                    print(f"  найден маркер: '{marker}'")

        page.wait_for_timeout(2000)

    browser.close()
print("\nГотово. Посмотри debug_ksk24_1.png и debug_ksk24_2.png")