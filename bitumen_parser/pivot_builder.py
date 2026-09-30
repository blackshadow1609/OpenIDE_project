"""
Построение pivot-таблиц для сравнения цен на мастику Технониколь.

Читает основной CSV (bitumen_prices.csv), нормализует названия товаров,
группирует позиции одного и того же продукта с разных сайтов и строит:

    output/bitumen_prices_pivot.csv     — плоская: по строке на источник
    output/bitumen_prices_summary.csv   — агрегированная: по строке на товар,
                                          с указанием минимальной цены,
                                          источника и разницы цен

Запуск:
    python pivot_builder.py
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger("pivot")

# --- Пути ---
PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"
INPUT_CSV = OUTPUT_DIR / "bitumen_prices.csv"
PIVOT_CSV = OUTPUT_DIR / "bitumen_prices_pivot.csv"
SUMMARY_CSV = OUTPUT_DIR / "bitumen_prices_summary.csv"


# ---------- Алиасы: ручные правила для «сокращённых» обозначений ----------

# Каждая группа: (regex, канонический ярлык)
# Применяется к нормализованному (lower) названию по очереди.
# ВАЖНО: порядок важен — более специфичные правила выше.
PRODUCT_ALIASES: list[tuple[str, str]] = [
    # --- Мастика №23 Фиксер (клей для гибкой черепицы / Шинглас Фиксер) ---
    (r"\bфиксер\b",                                    "n23_фиксер"),
    # «Фиксер Шинглас» — тот же продукт, ловим по слову Фиксер (выше).

    # --- №21 Техномаст (кровельная) ---
    (r"\bтехномаст\b",                                 "n21_техномаст"),
    (r"n\s*21\b|№\s*21\b",                             "n21"),

    # --- №22 Вишера (приклеивающая) ---
    (r"\bвишера\b",                                    "n22_вишера"),
    (r"n\s*22\b|№\s*22\b",                             "n22"),

    # --- №24 МГТН (гидроизоляционная) ---
    (r"\bмгтн\b",                                      "n24_мгтн"),
    (r"n\s*24\b|№\s*24\b",                             "n24"),

    # --- №27 приклеивающая ---
    (r"n\s*27\b|№\s*27\b",                             "n27"),

    # --- №31 кровельная морозостойкая ---
    (r"n\s*31\b|№\s*31\b",                             "n31"),

    # --- №33 водоэмульсионная ---
    (r"n\s*33\b|№\s*33\b",                             "n33"),

    # --- №41 Эврика ---
    (r"\bэврика\b",                                    "n41_эврика"),
    (r"n\s*41\b|№\s*41\b",                             "n41"),

    # --- №57 защитная алюминиевая ---
    (r"n\s*57\b|№\s*57\b",                             "n57"),

    # --- Пламя Стоп ---
    (r"пламя\s*стоп",                                  "пламя_стоп"),
]


# Слова-шум, удаляемые из названия ПЕРЕД алиасами.
# После алиасов мы получим канонический ярлык, и шум уже не помешает.
NOISE_WORDS = [
    # Общие слова
    "мастика", "технониколь", "technonikol", "техно", "николь",
    # Описания применения
    "кровельная", "приклеивающая", "гидроизоляционная", "защитная",
    "алюминиевая", "горячая", "морозостойкая", "водоэмульсионная",
    "битумная", "изоляционная", "универсальная", "ремонт", "и",
    # Суб-бренды и вторичные названия
    "шинглас", "shinglas", "клей", "для", "гибкой", "черепицы",
    "картридж",
    # Единицы продажи и артикулы
    "ведро", "вед", "меш", "руб", "шт", "штук", "млн",
]


def _strip_noise(s: str) -> str:
    """Убираем шумовые слова из строки (они не помогают идентификации)."""
    for w in NOISE_WORDS:
        s = re.sub(rf"\b{re.escape(w)}\b", " ", s)
    return s


def _canonical_marker(s: str) -> Optional[str]:
    """Прогоняем через таблицу алиасов — возвращаем первый совпавший ярлык."""
    for pattern, label in PRODUCT_ALIASES:
        if re.search(pattern, s, flags=re.IGNORECASE):
            return label
    return None


def _canonical_package(s: str) -> Optional[str]:
    """
    Каноничная фасовка: «20 кг», «3.6 кг», «310 мл» и т.п.
    Единицы нормализуем: килограмм → кг, литр → л, миллилитр → мл, штук → шт.
    """
    if not s:
        return None

    # Убираем №NN — на всякий случай, чтобы не путать с фасовкой
    s_clean = re.sub(r"№\s*\d+", " ", s)
    s_clean = re.sub(r"\bn\s*\d+\b", " ", s_clean, flags=re.IGNORECASE)

    # Ищем все «число + единица» и берём ПОСЛЕДНЕЕ (фасовка в конце названия)
    matches = re.findall(
        r"(\d+(?:[.,]\d+)?)\s*(кг|г|л|мл|шт|литр(?:ов|а)?|штук(?:а|и)?)\b",
        s_clean, flags=re.IGNORECASE,
    )
    if not matches:
        return None

    number_raw, raw_unit = matches[-1]
    number = number_raw.replace(",", ".")
    u = raw_unit.lower()
    if u.startswith("литр"):
        unit = "л"
    elif u.startswith("штук"):
        unit = "шт"
    else:
        unit = u

    # Нормализация: 20.0 кг → 20 кг, 3.60 кг → 3.6 кг
    if "." in number:
        number = number.rstrip("0").rstrip(".")

    return f"{number}{unit}"


def _normalize_name(raw: str) -> str:
    """
    Итоговый канонический ключ группы.

    Примеры:
        «Мастика кровельная ТН №21 (Техномаст), ведро 20кг»
            → "n21_техномаст 20кг"
        «Мастика №21 кровельная ТехноНиколь (Техномаст) 20кг»
            → "n21_техномаст 20кг"
        «Мастика приклеивающая ТН №23 (Фиксер) 12 кг»
            → "n23_фиксер 12кг"
        «Мастика (клей) для гибкой черепицы 12кг ТЕХНОНИКОЛЬ Шинглас Фиксер»
            → "n23_фиксер 12кг"
    """
    if not raw:
        return ""

    s = raw.lower()

    # 1. Достаём фасовку из ОРИГИНАЛЬНОГО названия (до чистки)
    package = _canonical_package(s)

    # 2. Чистим шум
    s = _strip_noise(s)

    # 3. Достаём маркер продукта (n21, n24, фиксер...)
    marker = _canonical_marker(s)

    # 4. Если маркер не нашли — пробуем на исходной строке
    if not marker:
        marker = _canonical_marker(raw.lower())

    # 5. Собираем ключ
    parts = []
    if marker:
        parts.append(marker)
    if package:
        parts.append(package)

    if not parts:
        # Fallback — первые 50 символов нормализованного имени
        return re.sub(r"\s+", " ", s).strip()[:50]

    return " ".join(parts)


# ---------- Основной пайплайн ----------

def load_main_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        logger.error("Файл %s не найден — сначала запусти main.py", path)
        sys.exit(1)
    df = pd.read_csv(path, encoding="utf-8-sig")
    logger.info("Загружено %d строк из %s", len(df), path)
    return df


def build_pivot(df: pd.DataFrame) -> pd.DataFrame:
    """Добавляем колонку с нормализованным ключом продукта."""
    df = df.copy()
    df["normalized_key"] = df["product_name"].apply(
        lambda x: _normalize_name(str(x) if pd.notna(x) else "")
    )
    # Fallback package_size
    df["package_size_filled"] = df.apply(
        lambda r: r["package_size"]
        if isinstance(r["package_size"], str) and r["package_size"]
        else None,
        axis=1,
    )
    return df


def build_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Агрегация: одна строка на нормализованный ключ.
    Колонки:
        normalized_key
        product_name_sample  — самое «человекочитаемое» название в группе
        package_size
        sources              — список источников через запятую
        n_offers             — всего предложений в группе
        n_with_price         — сколько с указанной ценой
        min_price            — минимальная цена
        min_price_source     — где дешевле
        max_price            — максимальная
        spread               — разница между max и min (в рублях)
        spread_pct           — разница в % от min
    """
    rows: list[dict[str, Any]] = []

    for key, group in df.groupby("normalized_key", sort=True):
        group = group.copy()
        priced = group[group["price"].notna()]

        name_sample = ""
        names = group["product_name"].dropna().astype(str)
        if not names.empty:
            name_sample = max(names, key=len)

        package_size = None
        pkgs = group["package_size_filled"].dropna().astype(str)
        if not pkgs.empty:
            package_size = pkgs.iloc[0]

        sources = sorted(group["source"].dropna().unique().tolist())

        if not priced.empty:
            min_idx = priced["price"].idxmin()
            max_idx = priced["price"].idxmax()
            min_price = float(priced.loc[min_idx, "price"])
            min_source = str(priced.loc[min_idx, "source"])
            max_price = float(priced.loc[max_idx, "price"])
            spread = max_price - min_price
            spread_pct = (spread / min_price * 100) if min_price > 0 else 0.0
        else:
            min_price = None
            min_source = None
            max_price = None
            spread = None
            spread_pct = None

        rows.append({
            "normalized_key": key,
            "product_name_sample": name_sample,
            "package_size": package_size,
            "sources": ", ".join(sources),
            "n_offers": len(group),
            "n_with_price": len(priced),
            "min_price": min_price,
            "min_price_source": min_source,
            "max_price": max_price,
            "spread": spread,
            "spread_pct": spread_pct,
        })

    summary = pd.DataFrame(rows)
    # Сортировка: сначала группы с наибольшей разницей, потом по min_price
    if not summary.empty:
        summary = summary.sort_values(
            by=["n_with_price", "spread", "min_price"],
            ascending=[False, False, True],
            na_position="last",
        ).reset_index(drop=True)
    return summary


def print_summary(summary: pd.DataFrame) -> None:
    logger.info("=" * 80)
    logger.info("СВОДКА: %d уникальных товарных групп", len(summary))
    logger.info("=" * 80)

    # --- Группы с несколькими источниками и хотя бы двумя ценами ---
    comparable = summary[(summary["n_offers"] >= 2) & (summary["n_with_price"] >= 2)]
    if not comparable.empty:
        logger.info("")
        logger.info("ГРУППЫ С РЕАЛЬНОЙ РАЗНИЦЕЙ ЦЕН (сравнение):")
        logger.info("%-58s | %-8s | %10s | %12s | %10s", "Товар", "Фасовка", "Мин ₽", "Макс ₽", "Разница")
        logger.info("-" * 120)
        for _, row in comparable.iterrows():
            logger.info(
                "%-58s | %-8s | %10.2f | %12.2f | %+10.2f (%.1f%%)",
                str(row["product_name_sample"])[:58],
                str(row["package_size"] or "?"),
                row["min_price"],
                row["max_price"],
                row["spread"],
                row["spread_pct"],
            )

    # --- Группы, где цена есть только у одного источника ---
    one_price = summary[(summary["n_with_price"] == 1)]
    if not one_price.empty:
        logger.info("")
        logger.info("ГРУППЫ С ОДНИМ ИСТОЧНИКОМ ЦЕНЫ (%d):", len(one_price))
        for _, row in one_price.iterrows():
            logger.info(
                "  - %-58s | %8.2f ₽ | %s",
                str(row["product_name_sample"])[:58],
                row["min_price"],
                row["min_price_source"],
            )

    # --- Группы вообще без цены ---
    no_price = summary[summary["n_with_price"] == 0]
    if not no_price.empty:
        logger.info("")
        logger.info("ГРУППЫ БЕЗ ИЗВЕСТНОЙ ЦЕНЫ (%d):", len(no_price))
        for _, row in no_price.head(15).iterrows():
            logger.info("  - %s", str(row["product_name_sample"])[:70])


# ---------- Точка входа ----------

def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(OUTPUT_DIR / "pivot.log", mode="w", encoding="utf-8"),
        ],
    )

    logger.info("Старт построения pivot-таблицы")

    df = load_main_csv(INPUT_CSV)
    if df.empty:
        logger.warning("Основной CSV пуст")
        return 0

    df_pivot = build_pivot(df)

    # 1) Плоская выгрузка
    df_pivot.to_csv(PIVOT_CSV, index=False, encoding="utf-8-sig")
    logger.info("Pivot (flat) сохранён: %s (%d строк)", PIVOT_CSV, len(df_pivot))

    # 2) Агрегированная выгрузка
    summary = build_summary(df_pivot)
    summary.to_csv(SUMMARY_CSV, index=False, encoding="utf-8-sig")
    logger.info("Summary сохранён: %s (%d строк)", SUMMARY_CSV, len(summary))

    # 3) Печать в консоль
    print_summary(summary)

    logger.info("Готово")
    return 0


if __name__ == "__main__":
    sys.exit(main())