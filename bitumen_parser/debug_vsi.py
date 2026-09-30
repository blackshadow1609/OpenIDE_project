"""
Диагностика страницы vseinstrumenti.ru.
Открывает видимый браузер, ждёт полной загрузки SPA,
сохраняет HTML и скриншот.
"""

from playwright.sync_api import sync_playwright
import time

URLS = [
    "https://www.vseinstrumenti.ru/search/?q=мастика",
    "https://www.vseinstrumenti.ru/search/?q=битумная+мастика+технониколь",
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

        # Ждём пока сеть «успокоится» после всех SPA-редиректов.
        # Если не получилось за 20 сек — не страшно, идём дальше.
        try:
            page.wait_for_load_state("networkidle", timeout=20000)
            print("networkidle OK")
        except Exception as e:
            print("networkidle timeout:", e)

        # Дадим ещё чуть-чуть на рендер
        page.wait_for_timeout(3000)

        print("Текущий URL:", page.url)
        print("Заголовок:", page.title())

        # Аккуратно сохраняем HTML — с retry, т.к. SPA мог ещё раз мигнуть
        html = None
        for attempt in range(3):
            try:
                html = page.content()
                break
            except Exception as e:
                print(f"content() attempt {attempt+1} failed:", e)
                time.sleep(2)
        if html:
            fname = f"debug_vsi_{i}.html"
            with open(fname, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"HTML сохранён: {fname}, длина = {len(html)}")
        else:
            print("HTML не удалось получить")

        # Скриншот (визуально видно, что происходит)
        try:
            page.screenshot(path=f"debug_vsi_{i}.png", full_page=False)
            print(f"Скриншот: debug_vsi_{i}.png")
        except Exception as e:
            print("screenshot error:", e)

        # Быстрый поиск характерных маркеров в HTML
        if html:
            for marker in ["product-card", "productCard", "product-item",
                           "Ничего не найдено", "ничего не нашлось",
                           "captcha", "cf-challenge", "проверка браузера"]:
                if marker.lower() in html.lower():
                    print(f"  найден маркер: '{marker}'")

        page.wait_for_timeout(2000)

    browser.close()
print("\nГотово. Посмотри debug_vsi_1.png и debug_vsi_2.png")