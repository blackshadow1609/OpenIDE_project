"""Отладка извлечения цены и бренда на ksk24.ru."""
import logging
logging.basicConfig(level=logging.WARNING)

from parsers.parser_ksk24 import ParserKsk24

with ParserKsk24() as p:
    p._warmup()
    p._safe_goto("https://ksk24.ru/search/?q=" + "мастика".replace(" ", "+"))
    sel = p._wait_for_any_selector(
        ['li.products__item', 'li[data-product-id]'], timeout_ms=15000
    )
    print("card selector:", sel)
    cards = p._page.query_selector_all(sel)
    print("найдено карточек:", len(cards))
    print("=" * 60)

    for i, card in enumerate(cards[:25], start=1):
        # Название
        name = p._extract_name(card)
        # Цена — сырой текст
        price_el = card.query_selector('span.products__price')
        price_raw = (price_el.inner_text() if price_el else None)
        # Дополнительно: content-атрибут
        price_attr = (price_el.get_attribute("content") if price_el else None)
        # URL
        url = p._extract_url(card)

        print(f"[{i}] {name}")
        print(f"    price_el={'есть' if price_el else 'НЕТ'}, "
              f"raw={price_raw!r}, content={price_attr!r}")
        print(f"    url={url}")
        print()