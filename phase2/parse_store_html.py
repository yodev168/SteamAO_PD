"""
parse_store_html.py

Parse a store page HTML file (cookie fallback) into a flat dict of master fields.
Uses BeautifulSoup to extract name, price, discount, release_date.
"""

import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from date_utils import normalize_release_date


# TWD symbol and currency code patterns
_PRICE_RE = re.compile(r"NT\$\s*([\d,]+(?:\.\d+)?)|(\d[\d,]+(?:\.\d+)?)\s*TWD", re.IGNORECASE)
_USD_RE = re.compile(r"US\$\s*([\d,]+(?:\.\d+)?)|USD\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)


def _parse_twd_to_int(price_str: str) -> int | None:
    """Convert a price string like 'NT$249' or '249 TWD' to integer TWD (NT$249 → 249)."""
    price_str = price_str.strip().replace(",", "")
    m = _PRICE_RE.search(price_str)
    if m:
        raw = m.group(1) or m.group(2)
        try:
            return int(float(raw))
        except ValueError:
            return None
    return None


def _parse_usd_to_float(price_str: str) -> float | None:
    """Convert a price string like 'US$9.99' to float USD (9.99)."""
    price_str = price_str.strip().replace(",", "")
    m = _USD_RE.search(price_str)
    if m:
        raw = m.group(1) or m.group(2)
        try:
            return round(float(raw), 2)
        except ValueError:
            return None
    return None


def parse_store_html(appid: int, path: Path) -> dict[str, Any] | None:
    """
    Read raw/html/<appid>.html and return master-fields dict, or None on failure.

    Returned keys:
        appid, name, price_twd_original, price_usd_original,
        lowest_discount_percent, lowest_price_twd, lowest_price_usd,
        is_free, release_date, coming_soon, source_appdetails, source_html_fallback
    """
    if not path.exists():
        return None

    try:
        html = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # --- name ---
    name: str = ""
    title_div = soup.select_one("div.apphub_AppName") or soup.select_one("#appHubAppName")
    if title_div:
        name = title_div.get_text(strip=True)
    if not name:
        og_title = soup.find("meta", property="og:title")
        if og_title:
            name = og_title.get("content", "").strip()
    if not name:
        return None

    # --- free / price ---
    is_free = False
    price_twd_original: int | None = None
    price_usd_original: float | None = None

    # "Free to Play" / "Free" badge
    free_tag = soup.select_one("div.game_area_purchase_game_wrapper .game_purchase_price")
    if free_tag:
        text = free_tag.get_text(strip=True).lower()
        if "free" in text:
            is_free = True
            price_twd_original = 0
            price_usd_original = 0.0

    if not is_free:
        # Original (pre-discount) price, preferred.
        original_el = soup.select_one("div.discount_original_price")
        if original_el:
            raw_original = original_el.get_text(strip=True)
            price_twd_original = _parse_twd_to_int(raw_original)
            price_usd_original = _parse_usd_to_float(raw_original)

        # No discount block: fallback to regular single price label.
        if price_twd_original is None:
            regular_el = soup.select_one("div.game_purchase_price") or soup.select_one("div.discount_final_price")
            if regular_el:
                raw_regular = regular_el.get_text(strip=True)
                if "free" in raw_regular.lower():
                    is_free = True
                    price_twd_original = 0
                    price_usd_original = 0.0
                else:
                    price_twd_original = _parse_twd_to_int(raw_regular)
                    if price_usd_original is None:
                        price_usd_original = _parse_usd_to_float(raw_regular)

    # --- release_date ---
    release_date: str | None = None
    coming_soon = False

    date_el = soup.select_one("div.date")
    if date_el:
        release_date = date_el.get_text(strip=True) or None

    if not release_date:
        # Try structured date in the right-column details
        for detail in soup.select("div.details_block"):
            text = detail.get_text(separator=" ", strip=True)
            if "發售日" in text or "release date" in text.lower():
                parts = text.split(":", 1)
                if len(parts) == 2:
                    release_date = parts[1].strip() or None
                break

    # Detect "Coming Soon" / "TBA"
    if release_date:
        low = release_date.lower()
        if "coming soon" in low or "tba" in low or "即将推出" in low or "即將推出" in low:
            coming_soon = True
    else:
        # Check if there's a "coming soon" notice anywhere prominent
        for tag in soup.select("h1, h2, .game_area_comingsoon"):
            if "coming soon" in tag.get_text(strip=True).lower():
                coming_soon = True
                release_date = "Coming Soon"
                break

    release_date = normalize_release_date(release_date)

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
        "source_appdetails": False,
        "source_html_fallback": True,
    }
