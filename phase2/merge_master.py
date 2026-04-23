"""
merge_master.py

Merge appdetails, HTML fallback, and reviews data into ao_games_master.csv.

Merge logic per appid:
  1. Try parse_appdetails  (source_appdetails = True)
  2. If that returns None, try parse_store_html  (source_html_fallback = True)
  3. Layer in parse_reviews for review fields (always, independent of above)
  4. Fill missing fields with None / defaults

Run:
    cd phase2
    python merge_master.py
"""

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    MASTER_CSV,
    RAW_APPDETAILS_DIR,
    RAW_HTML_DIR,
    RAW_REVIEWS_DIR,
)
from load_appids import load_appids
from parse_appdetails import parse_appdetails
from parse_reviews import parse_reviews
from parse_store_html import parse_store_html

MASTER_FIELDS = [
    "appid",
    "name",
    "price_twd_original",
    "price_usd_original",
    "lowest_discount_percent",
    "lowest_price_twd",
    "lowest_price_usd",
    "is_free",
    "release_date",
    "coming_soon",
    "developer",
    "publisher",
    "header_image",
    "genres",
    "categories",
    "recommendations_total",
    "review_count",
    "review_positive",
    "review_negative",
    "review_score",
    "review_score_desc",
    "positive_ratio",
    "has_reviews",
    "source_appdetails",
    "source_html_fallback",
    "fetched_at",
]

REVIEW_DEFAULTS = {
    "review_count": 0,
    "review_positive": 0,
    "review_negative": 0,
    "review_score": 0,
    "review_score_desc": "",
    "positive_ratio": None,
    "has_reviews": False,
}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def merge_row(appid: int, name: str, ts: str) -> dict:
    """Build one master row for the given appid."""

    # 1. appdetails (primary)
    base = parse_appdetails(appid, RAW_APPDETAILS_DIR / f"{appid}.json")

    # 2. HTML fallback if appdetails unusable
    if base is None:
        base = parse_store_html(appid, RAW_HTML_DIR / f"{appid}.html")

    # 3. Still nothing — use the name we already have from phase1
    if base is None:
        base = {
            "appid": appid,
            "name": name,
            "price_twd_original": None,
            "price_usd_original": None,
            "lowest_discount_percent": None,
            "lowest_price_twd": None,
            "lowest_price_usd": None,
            "is_free": False,
            "release_date": None,
            "coming_soon": False,
            "developer": "",
            "publisher": "",
            "header_image": "",
            "genres": "",
            "categories": "",
            "recommendations_total": None,
            "source_appdetails": False,
            "source_html_fallback": False,
        }

    # 4. Reviews (independent layer)
    rev = parse_reviews(appid, RAW_REVIEWS_DIR / f"{appid}.json")
    if rev:
        base.update({k: rev[k] for k in REVIEW_DEFAULTS})
    else:
        base.update(REVIEW_DEFAULTS)

    # 5. Timestamp
    base["fetched_at"] = ts

    # 6. Ensure all fields present with defaults
    for field in MASTER_FIELDS:
        base.setdefault(field, None)

    return base


def run() -> None:
    entries = load_appids()
    total = len(entries)
    ts = now_iso()

    print(f"[START] {ts}  merging {total} appids → {MASTER_CSV.name}")

    rows: list[dict] = []
    no_data = 0
    no_reviews = 0

    for idx, (appid, name) in enumerate(entries, 1):
        row = merge_row(appid, name, ts)
        rows.append(row)

        if not row["source_appdetails"] and not row["source_html_fallback"]:
            no_data += 1
        if row["review_count"] == 0 and row["review_score"] == 0:
            no_reviews += 1

        if idx % 1000 == 0 or idx == total:
            print(f"  merged {idx}/{total} ...")

    # Write CSV
    try:
        with open(MASTER_CSV, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=MASTER_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    except PermissionError:
        print(
            f"[ERROR] Cannot write {MASTER_CSV} (Permission denied).\n"
            "  Please close any app that is using this CSV (Excel/editor preview), then retry."
        )
        sys.exit(1)

    print(f"\n[DONE]  {now_iso()}")
    print(f"        Rows written : {len(rows)}")
    print(f"        No source data (name from phase1 only) : {no_data}")
    print(f"        No reviews data : {no_reviews}")
    print(f"        Output: {MASTER_CSV}")
    print(f"  Next: python sanity_check.py")


if __name__ == "__main__":
    run()
