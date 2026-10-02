"""
Главный модуль проекта «Сравнение цен на битумную мастику Технониколь».

Запускает парсеры ТРЁХ сайтов стройматериалов:
    1. ksk24.ru        — каталог ksk24
    2. tophouse.ru     — поиск tophouse
    3. td-marman.ru    — каталог «Мастики ТЕХНОНИКОЛЬ»

Объединяет результаты, выгружает в CSV и печатает краткую сводку.

Запуск:
    python main.py

Результат:
    output/bitumen_prices.csv   — итоговая таблица
    output/parser.log           — лог работы
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import pandas as pd

# --- Парсеры ---
from parsers.parser_ksk24 import ParserKsk24
from parsers.parser_tophouse import ParserTophouse
from parsers.parser_td_marman import ParserTdMarman


# ---------- Пути ----------
PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"
CSV_PATH = OUTPUT_DIR / "bitumen_prices.csv"
LOG_PATH = OUTPUT_DIR / "parser.log"

# Колонки итогового CSV (в этом порядке)
CSV_COLUMNS = [
    "product_name",
    "price",
    "unit",
    "package_size",
    "availability",
    "url",
    "source",
    "scrape_timestamp",
]


# ---------- Логирование ----------
def setup_logging() -> None:
    """
    Логи пишем одновременно в файл и в консоль.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    formatter = logging.Formatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    # Файл
    fh = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
    fh.setFormatter(formatter)
    root.addHandler(fh)

    # Консоль
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    root.addHandler(ch)


logger = logging.getLogger("main")


# ---------- Запуск парсеров ----------
def run_parser(parser_cls, label: str) -> list[dict[str, Any]]:
    """
    Запустить один парсер в контекстном менеджере и вернуть список записей.
    Любые исключения логируем, но не валим весь пайплайн.
    """
    if parser_cls is None:
        logger.info("Парсер '%s' не подключён — пропускаем", label)
        return []

    logger.info("=" * 60)
    logger.info("Запускаем парсер: %s", label)
    logger.info("=" * 60)

    try:
        with parser_cls() as p:
            rows = p.parse()
        logger.info("[%s] Получено записей: %d", label, len(rows))
        return rows
    except Exception as e:
        logger.exception("[%s] Парсер завершился с ошибкой: %s", label, e)
        return []


# ---------- Обработка данных ----------
def normalize_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Приводим все записи к единому виду:
      - гарантируем наличие всех колонок из CSV_COLUMNS;
      - обрезаем пробелы в строковых полях;
      - цена — либо float, либо None.
    """
    normalized: list[dict[str, Any]] = []
    for r in records:
        row = {col: r.get(col) for col in CSV_COLUMNS}

        # Строковые поля — strip + None для пустых
        for key in (
                "product_name", "unit", "package_size",
                "availability", "url", "source", "scrape_timestamp",
        ):
            val = row.get(key)
            if isinstance(val, str):
                val = val.strip()
                row[key] = val or None

        # Цена — float или None
        price = row.get("price")
        if isinstance(price, (int, float)):
            row["price"] = float(price)
        else:
            row["price"] = None

        normalized.append(row)
    return normalized


def build_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Собираем DataFrame с правильным порядком колонок и сортировкой."""
    if not records:
        return pd.DataFrame(columns=CSV_COLUMNS)

    df = pd.DataFrame(records, columns=CSV_COLUMNS)

    # Сортировка: сначала по источнику, потом по названию
    df = df.sort_values(
        by=["source", "product_name"], na_position="last"
    ).reset_index(drop=True)
    return df


def save_csv(df: pd.DataFrame, path: Path) -> None:
    """Сохраняем CSV в UTF-8 с BOM — так Excel корректно откроет кириллицу."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    logger.info("CSV сохранён: %s (%d строк)", path, len(df))


def print_summary(df: pd.DataFrame) -> None:
    """Краткая сводка в консоль."""
    logger.info("=" * 60)
    logger.info("СВОДКА")
    logger.info("=" * 60)

    if df.empty:
        logger.warning("Нет данных для отчёта")
        return

    # Сколько всего позиций
    total = len(df)
    logger.info("Всего позиций: %d", total)

    # По источникам
    by_source = df.groupby("source").agg(
        total=("product_name", "count"),
        with_price=("price", lambda s: s.notna().sum()),
    )
    logger.info("По источникам:")
    for source, row in by_source.iterrows():
        logger.info(
            "  - %-25s всего: %3d | с ценой: %3d",
            source, int(row["total"]), int(row["with_price"]),
        )

    # Топ-7 самых дешёвых (только с ценой)
    priced = df[df["price"].notna()].copy()
    if not priced.empty:
        priced = priced.sort_values("price").head(7)
        logger.info("Топ-7 самых дешёвых позиций (с указанной ценой):")
        for _, row in priced.iterrows():
            logger.info(
                "  - %-60s | %9.2f ₽ | %s",
                (row["product_name"] or "")[:60],
                row["price"],
                row["source"],
            )
    else:
        logger.info("Позиций с указанной ценой нет.")

    # Уникальных источников
    logger.info("Уникальных источников: %d", df["source"].nunique())
    logger.info("Сохранено в: %s", CSV_PATH)


# ---------- Точка входа ----------
def main() -> int:
    setup_logging()
    logger.info("Старт сбора цен на мастику Технониколь")

    # Список парсеров в порядке обхода
    parsers: list[tuple[Any, str]] = [
        (ParserKsk24,    "ksk24.ru"),
        (ParserTophouse, "tophouse.ru"),
        (ParserTdMarman, "td-marman.ru"),
    ]

    # Собираем все записи
    all_records: list[dict[str, Any]] = []
    for parser_cls, label in parsers:
        rows = run_parser(parser_cls, label)
        all_records.extend(rows)

    logger.info("=" * 60)
    logger.info("Всего собрано записей: %d", len(all_records))

    # Нормализация + DataFrame + сохранение
    normalized = normalize_records(all_records)
    df = build_dataframe(normalized)
    save_csv(df, CSV_PATH)

    # Сводка в консоль
    print_summary(df)

    logger.info("Готово")
    return 0


if __name__ == "__main__":
    sys.exit(main())