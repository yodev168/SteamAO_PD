"""
data.py — Phase 5
Loads phase3/ao_games_cleaned.csv, applies type conversions,
and exposes helpers for the dashboard.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_BASE = Path(__file__).parent
CSV_PATH = _BASE.parent / "phase3" / "ao_games_cleaned.csv"

# ---------------------------------------------------------------------------
# review_score_desc → Chinese mapping
# ---------------------------------------------------------------------------
SCORE_DESC_ZH: dict[str, str] = {
    "Overwhelmingly Positive": "壓倒性好評",
    "Very Positive":           "極度好評",
    "Positive":                "好評",
    "Mostly Positive":         "大多好評",
    "Mixed":                   "褒貶不一",
    "Mostly Negative":         "大多負評",
    "Negative":                "負評",
    "Very Negative":           "極度負評",
    "No user reviews":         "尚無評論",
}

# Ratings that represent "named" review bands (not "N user reviews")
NAMED_RATINGS: list[str] = list(SCORE_DESC_ZH.keys())

# Sort order for filter display (best → worst)
RATING_DISPLAY_ORDER: list[str] = [
    "壓倒性好評", "極度好評", "大多好評", "好評",
    "褒貶不一",
    "大多負評", "負評", "極度負評",
    "尚無評論",
]


def _normalise_score_desc(val: str) -> str:
    """Return canonical Chinese label, or '少量評論' for '# user reviews' strings."""
    val = (val or "").strip()
    if val in SCORE_DESC_ZH:
        return SCORE_DESC_ZH[val]
    if "user review" in val.lower():
        return "少量評論"
    return val or "—"


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="載入遊戲資料中…")
def load_games() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig", low_memory=False)

    # Numeric columns
    for col in ["price_twd_original", "price_usd_original",
                "review_count", "review_positive", "review_negative",
                "review_score", "positive_ratio", "est_sales_low"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Date
    df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce")
    df["release_year"]  = pd.to_numeric(df["release_date"].dt.year,  errors="coerce")
    df["release_month"] = pd.to_numeric(df["release_date"].dt.month, errors="coerce")

    # Chinese review score
    df["review_score_desc_zh"] = df["review_score_desc"].apply(_normalise_score_desc)

    # est_sales_low: fill 0 if missing
    df["est_sales_low"] = df["est_sales_low"].fillna(0).astype(int)

    # Ensure appid is string for URL building
    df["appid"] = df["appid"].astype(str)

    return df


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def steam_url(appid: str) -> str:
    return f"https://store.steampowered.com/app/{appid}"


def fmt_twd(val) -> str:
    try:
        return f"NT$ {int(val):,}"
    except (TypeError, ValueError):
        return "—"


def fmt_usd(val) -> str:
    try:
        return f"US$ {float(val):.2f}"
    except (TypeError, ValueError):
        return "—（資料補齊中）"


def fmt_num(val) -> str:
    try:
        return f"{int(val):,}"
    except (TypeError, ValueError):
        return "—"


# ---------------------------------------------------------------------------
# Sort options (shared between app.py and pages)
# ---------------------------------------------------------------------------
SORT_OPTIONS: dict[str, tuple[str, bool]] = {
    "預測銷售套數（高→低）": ("est_sales_low", False),
    "評論數量（高→低）":     ("review_count", False),
    "發售日期（新→舊）":     ("release_date", False),
    "發售日期（舊→新）":     ("release_date", True),
    "台幣售價（高→低）":     ("price_twd_original", False),
    "台幣售價（低→高）":     ("price_twd_original", True),
    "好評率（高→低）":       ("positive_ratio", False),
}


def display_value(val) -> str:
    """Return '—（資料補齊中）' when value is blank/NaN."""
    if val is None:
        return "—（資料補齊中）"
    s = str(val).strip()
    if s == "" or s == "nan":
        return "—（資料補齊中）"
    return s
