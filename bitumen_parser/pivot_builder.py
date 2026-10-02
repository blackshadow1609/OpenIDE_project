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


# ---------- Исключения: не-мастики ----------

# Если название содержит «герметик», но НЕ содержит «мастика» — это не наш товар
EXCLUDE_IF_HERMETIC_AND_NOT_MASTIKA = re.compile(
    r"герметик", flags=re.IGNORECASE,
)
INCLUDE_MASTIKA = re.compile(
    r"мастика", flags=re.IGNORECASE,
)


# ---------- Алиасы: ручные правила для «сокращённых» обозначений ----------

PRODUCT_ALIASES: list[tuple[str, str]] = [
    # --- Мастика №23 Фиксер (клей для гибкой черепицы / Шинглас Фиксер) ---
    (r"\bфиксер\b",                                    "n23_фиксер"),

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

    # --- НОВЫЕ (от td-marman) ---
    # --- №71 герметизирующая (всё же мастика, хоть и герметизирующая) ---
    (r"n\s*71\b|№\s*71\b",                             "n71"),

    # --- МБР-65 / МБР-75 / МБР-90 (битумно-резиновые) ---
    (r"мбр[\s\-]*65",                                  "мбр65"),
    (r"мбр[\s\-]*75",                                  "мбр75"),
    (r"мбр[\s\-]*90",                                  "мбр90"),

    # --- Пламя Стоп ---
    (r"пламя\s*стоп",                                  "пламя_стоп"),
]


# ---------- Унификация фасовки для «пограничных» групп ----------
# Эти маркеры принудительно получают фиксированную фасовку,
# даже если у источника её нет в названии.
FORCE_PACKAGE: dict[str, str] = {
    # Пламя Стоп у ТН существует только в фасовке 20 кг —
    # у ksk24 фасовка в названии не указана, подтягиваем её.
    "пламя_стоп": "20кг",
}

# Эти маркеры, наоборот, ИГНОРИРУЮТ фасовку:
# №31 у ksk24 в литрах (20,6 л), у td-marman в кг (18 кг) —
# это одна и та же мастика, сводим в одну группу.
IGNORE_PACKAGE_MARKERS: set[str] = {
    "n31",
}


# Слова-шум, удаляемые из названия ПЕРЕД алиасами.
NOISE_WORDS = [
    # Общие слова
    "мастика", "технониколь", "technonikol", "техно", "николь",
    # Описания применения
    "кровельная", "приклеивающая", "гидроизоляционная", "защитная",
    "алюминиевая", "горячая", "морозостойкая", "водоэмульсионная",
    "битумная", "изоляционная", "универсальная", "ремонт", "и",
    "герметизирующая", "битумно-резиновая", "битумно", "резиновая",
    # Суб-бренды и вторичные названия
    "шинглас", "shinglas", "клей", "для", "гибкой", "черепицы",
    "картридж", "ведро", "вед", "меш", "руб", "шт", "штук",
]


def _strip_noise(s: str) -> str:
    """Убираем шумовые слова из строки."""
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
    Каноничная фасовка: «20кг», «3.6кг», «310мл» и т.п.
    Убираем «№N», нормализуем единицы.
    """
    if not s:
        return None

    s_clean = re.sub(r"№\s*\d+", " ", s)
    s_clean = re.sub(r"\bn\s*\d+\b", " ", s_clean, flags=re.IGNORECASE)

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

    if "." in number:
        number = number.rstrip("0").rstrip(".")

    return f"{number}{unit}"


def _normalize_name(raw: str) -> str:
    """
    Итоговый канонический ключ группы.
    """
    if not raw:
        return ""

    s = raw.lower()

    # 1. Достаём фасовку из ОРИГИНАЛЬНОГО названия
    package = _canonical_package(s)

    # 2. Достаём маркер продукта (n21, n24, фиксер...)
    #    Сначала пробуем на полной строке (до чистки) — важно для «№ 21 Техномаст»
    marker = _canonical_marker(s)

    # 3. Если не нашли — чистим шум и пробуем снова
    if not marker:
        s_clean = _strip_noise(s)
        marker = _canonical_marker(s_clean)
    else:
        s_clean = _strip_noise(s)

    # 3a. Унификация фасовки для «пограничных» случаев
    if marker in FORCE_PACKAGE:
        package = FORCE_PACKAGE[marker]
    elif marker in IGNORE_PACKAGE_MARKERS:
        package = None

    # 4. Собираем ключ
    parts = []
    if marker:
        parts.append(marker)
    if package:
        parts.append(package)

    if not parts:
        return re.sub(r"\s+", " ", s_clean).strip()[:50]

    return " ".join(parts)


# ---------- Основной пайплайн ----------

def load_main_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        logger.error("Файл %s не найден — сначала запусти main.py", path)
        sys.exit(1)
    df = pd.read_csv(path, encoding="utf-8-sig")
    logger.info("Загружено %d строк из %s", len(df), path)
    return df


def filter_records(df: pd.DataFrame) -> pd.DataFrame:
    """
    Оставляем только мастики: если в названии есть «герметик» и нет «мастика» —
    исключаем. Это убирает случайный «Герметик битумно-полимерный №42».
    """
    before = len(df)

    def keep(name: str) -> bool:
        name = str(name)
        if EXCLUDE_IF_HERMETIC_AND_NOT_MASTIKA.search(name) \
                and not INCLUDE_MASTIKA.search(name):
            return False
        return True

    df = df[df["product_name"].apply(keep)].copy()
    after = len(df)
    if after < before:
        logger.info("Отфильтровано не-мастик: %d (осталось %d)", before - after, after)
    return df


def build_pivot(df: pd.DataFrame) -> pd.DataFrame:
    """Добавляем колонку с нормализованным ключом продукта."""
    df = df.copy()
    df["normalized_key"] = df["product_name"].apply(
        lambda x: _normalize_name(str(x) if pd.notna(x) else "")
    )
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
    """
    rows: list[dict[str, Any]] = []

    for key, group in df.groupby("normalized_key", sort=True):
        group = group.copy()
        priced = group[group["price"].notna()]

        name_sample = ""
        names = group["product_name"].dropna().astype(str)
        if not names.empty:
            name_sample = max(names, key=len)

        # Предпочитаем фасовку с мл/л, если такие есть, иначе первую
        package_size = None
        pkgs = group["package_size_filled"].dropna().astype(str).tolist()
        if pkgs:
            def score(p: str) -> int:
                p = p.lower()
                if "мл" in p:  return 0
                if " л" in p:  return 1
                if "кг" in p:  return 2
                return 3
            pkgs_sorted = sorted(pkgs, key=score)
            package_size = pkgs_sorted[0]

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
    if not summary.empty:
        summary = summary.sort_values(
            by=["n_with_price", "spread", "min_price"],
            ascending=[False, False, True],
            na_position="last",
        ).reset_index(drop=True)
    return summary


def print_summary(summary: pd.DataFrame) -> None:
    logger.info("=" * 90)
    logger.info("СВОДКА: %d уникальных товарных групп", len(summary))
    logger.info("=" * 90)

    # --- Группы с несколькими источниками и хотя бы двумя ценами ---
    comparable = summary[(summary["n_offers"] >= 2) & (summary["n_with_price"] >= 2)]
    if not comparable.empty:
        logger.info("")
        logger.info("ГРУППЫ С РЕАЛЬНОЙ РАЗНИЦЕЙ ЦЕН (сравнение):")
        logger.info("%-58s | %-8s | %10s | %12s | %10s",
                    "Товар", "Фасовка", "Мин ₽", "Макс ₽", "Разница")
        logger.info("-" * 130)
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

    # Фильтр не-мастик
    df = filter_records(df)

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