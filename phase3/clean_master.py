"""
clean_master.py — Phase 3

Read ao_games_master.csv, filter out free and unreleased games,
add est_sales_low = review_count * 200, write ao_games_cleaned.csv.

Run:
    cd phase3
    python clean_master.py
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import CLEANED_CSV, MASTER_CSV


def _is_free(row: dict) -> bool:
    """True if the game is marked free OR has a zero/blank price."""
    if row.get("is_free", "").strip() == "True":
        return True
    price = row.get("price_twd_original", "").strip()
    if price == "" or price == "0":
        return True
    return False


def _is_coming_soon(row: dict) -> bool:
    return row.get("coming_soon", "").strip() == "True"


def run() -> None:
    if not MASTER_CSV.exists():
        print(f"[ERROR] Master CSV not found: {MASTER_CSV}")
        sys.exit(1)

    with open(MASTER_CSV, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        original_fields = reader.fieldnames or []
        rows = list(reader)

    total = len(rows)

    kept = []
    dropped_free = 0
    dropped_soon = 0

    for row in rows:
        if _is_free(row):
            dropped_free += 1
            continue
        if _is_coming_soon(row):
            dropped_soon += 1
            continue
        kept.append(row)

    # Add est_sales_low
    for row in kept:
        try:
            review_count = int(row.get("review_count") or 0)
        except ValueError:
            review_count = 0
        row["est_sales_low"] = review_count * 200

    out_fields = list(original_fields) + ["est_sales_low"]

    try:
        with open(CLEANED_CSV, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=out_fields)
            writer.writeheader()
            writer.writerows(kept)
    except PermissionError:
        print(
            f"[ERROR] Cannot write {CLEANED_CSV} (Permission denied).\n"
            "  Please close any app that is using this CSV (Excel/editor preview), then retry."
        )
        sys.exit(1)

    dropped_total = dropped_free + dropped_soon
    print(f"[DONE] clean_master.py")
    print(f"       Input  : {MASTER_CSV.name}  ({total:,} rows)")
    print(f"       Dropped: free/zero-price={dropped_free:,}  coming_soon={dropped_soon:,}  total={dropped_total:,}")
    print(f"       Output : {CLEANED_CSV.name}  ({len(kept):,} rows)")
    print(f"  Next: review ao_games_cleaned.csv")


if __name__ == "__main__":
    run()
