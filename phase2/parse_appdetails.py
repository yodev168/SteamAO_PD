"""
parse_appdetails.py

Parse a raw appdetails JSON file into a flat dict of master fields.
Returns None if the appdetails response was success:false or empty.
"""

import json
from pathlib import Path
from typing import Any

from date_utils import normalize_release_date

def _extract_inner(raw: dict, appid: int) -> dict:
    """Extract Steam appdetails inner object: {'success': ..., 'data': ...}."""
    if not raw:
        return {}
    if str(appid) in raw:
        # Legacy format: full steam response stored directly.
        return raw.get(str(appid), {})
    if "tw" in raw:
        # New format: {"tw": <steam response>, "us": <steam response>}
        return raw.get("tw", {}).get(str(appid), {})
    return {}


def _extract_us_inner(raw: dict, appid: int) -> dict:
    """Extract optional US appdetails inner object from new multi-cc payload."""
    if not raw:
        return {}
    if "us" not in raw:
        return {}
    return raw.get("us", {}).get(str(appid), {})


def _to_twd_major(value: Any) -> int | None:
    """Convert Steam smallest-unit integer to TWD major unit integer."""
    if value is None:
        return None
    try:
        return int(value) // 100
    except (TypeError, ValueError):
        return None


def _to_usd_major(value: Any) -> float | None:
    """Convert Steam smallest-unit integer to USD major unit decimal."""
    if value is None:
        return None
    try:
        return round(int(value) / 100.0, 2)
    except (TypeError, ValueError):
        return None


def parse_appdetails(appid: int, path: Path) -> dict[str, Any] | None:
    """
    Read raw/appdetails/<appid>.json and return a master-fields dict,
    or None if the data is not usable.

    Returned keys:
        appid, name, price_twd_original, price_usd_original,
        lowest_discount_percent, lowest_price_twd, lowest_price_usd,
        is_free, release_date, coming_soon,
        developer, publisher, header_image, genres, categories,
        recommendations_total, source_appdetails
    """
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    inner = _extract_inner(data, appid)
    if not inner.get("success", False):
        return None

    game = inner.get("data")
    if not game:
        return None

    # --- name ---
    name: str = game.get("name") or ""

    # --- free / price ---
    is_free: bool = bool(game.get("is_free", False))
    price_twd_original: int | None = None
    price_usd_original: float | None = None

    price_overview = game.get("price_overview")
    if price_overview:
        # Keep only original-list price (not current discounted final price).
        price_twd_original = _to_twd_major(price_overview.get("initial"))
    elif is_free:
        price_twd_original = 0

    # Optional USD price from secondary appdetails request (cc=us).
    us_inner = _extract_us_inner(data, appid)
    us_game = us_inner.get("data") if us_inner.get("success", False) else None
    if us_game and us_game.get("price_overview"):
        price_usd_original = _to_usd_major(us_game["price_overview"].get("initial"))
    elif is_free:
        price_usd_original = 0.0

    # --- release_date ---
    release_date_obj = game.get("release_date", {})
    tw_release_date: str | None = release_date_obj.get("date") or None
    coming_soon: bool = bool(release_date_obj.get("coming_soon", False))

    us_release_date: str | None = None
    if us_game:
        us_release_obj = us_game.get("release_date", {})
        us_release_date = us_release_obj.get("date") or None
        coming_soon = coming_soon or bool(us_release_obj.get("coming_soon", False))

    # Prefer English/US release text when available.
    release_date: str | None = normalize_release_date(us_release_date or tw_release_date)

    # Treat blank string as None
    if release_date == "":
        release_date = None

    if not name:
        return None

    # --- developer / publisher ---
    developer: str = "|".join(game.get("developers") or [])
    publisher: str = "|".join(game.get("publishers") or [])

    # --- header_image ---
    header_image: str = game.get("header_image") or ""

    # --- genres ---
    genres: str = "|".join(
        g.get("description", "") for g in (game.get("genres") or [])
    )

    # --- categories ---
    categories: str = "|".join(
        c.get("description", "") for c in (game.get("categories") or [])
    )

    # --- recommendations ---
    recommendations_total: int | None = None
    rec = game.get("recommendations")
    if rec and isinstance(rec, dict):
        try:
            recommendations_total = int(rec.get("total", 0))
        except (TypeError, ValueError):
            recommendations_total = None

    return {
        "appid": appid,
        "name": name,
        "price_twd_original": price_twd_original,
        "price_usd_original": price_usd_original,
        "lowest_discount_percent": None,
        "lowest_price_twd": None,
        "lowest_price_usd": None,
        "is_free": is_free,
        "release_date": release_date,
        "coming_soon": coming_soon,
        "developer": developer,
        "publisher": publisher,
        "header_image": header_image,
        "genres": genres,
        "categories": categories,
        "recommendations_total": recommendations_total,
        "source_appdetails": True,
        "source_html_fallback": False,
    }
