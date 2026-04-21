"""
sanity_check.py

Validate Phase 1a output after running crawl_search.py + merge_export.py.

Checks:
  1. total_count consistency across all raw pages
  2. Raw record count vs deduped count (duplicate ratio)
  3. Deduped count vs Steam's total_count (±10 tolerance)
  4. Invalid appids (null / empty / non-numeric)
  5. Random sample of 3 appids for manual spot-check

Run:
    cd phase1
    python sanity_check.py
"""

import csv
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import DEDUPED_CSV, RAW_CSV, RAW_DIR


TOLERANCE = 10   # acceptable gap between deduped count and Steam total_count
SAMPLE_N = 3     # number of random appids to print for manual check


def load_raw_pages() -> tuple[list[dict], list[int]]:
    files = sorted(
        RAW_DIR.glob("search_start_*.json"),
        key=lambda p: int(p.stem.split("_")[-1]),
    )
    if not files:
        return [], []
    pages = []
    total_counts = []
    for path in files:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        pages.append(data)
        tc = data.get("total_count")
        if tc is not None:
            total_counts.append(tc)
    return pages, total_counts


def load_csv_appids(path: Path) -> list[str]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return [row["appid"] for row in reader]


def check(label: str, passed: bool, detail: str = "") -> bool:
    status = "PASS" if passed else "FAIL"
    line = f"  [{status}] {label}"
    if detail:
        line += f"  ({detail})"
    print(line)
    return passed


def main() -> None:
    print("=" * 55)
    print("  Phase 1a Sanity Check")
    print("=" * 55)

    all_passed = True

    # --- 1. Load raw pages ---
    pages, total_counts = load_raw_pages()
    page_count = len(pages)
    print(f"\n[RAW PAGES]  {page_count} files in {RAW_DIR}")

    ok = check("raw/ directory exists and has files", page_count > 0)
    all_passed = all_passed and ok

    # --- 2. total_count consistency ---
    unique_tc = set(total_counts)
    ok = check(
        "total_count is consistent across all pages",
        len(unique_tc) <= 1,
        f"values seen: {unique_tc}",
    )
    all_passed = all_passed and ok
    steam_total = max(total_counts) if total_counts else 0
    print(f"         Steam reports total_count = {steam_total}")

    # --- 3. CSV existence ---
    raw_appids = load_csv_appids(RAW_CSV)
    deduped_appids = load_csv_appids(DEDUPED_CSV)

    ok = check("ao_apps_raw.csv exists and has rows", len(raw_appids) > 0,
               f"{len(raw_appids)} rows")
    all_passed = all_passed and ok

    ok = check("ao_apps_deduped.csv exists and has rows", len(deduped_appids) > 0,
               f"{len(deduped_appids)} rows")
    all_passed = all_passed and ok

    # --- 4. Duplicate ratio ---
    dup_count = len(raw_appids) - len(deduped_appids)
    ok = check(
        "duplicate count is reasonable",
        dup_count >= 0,
        f"{dup_count} duplicates removed",
    )
    all_passed = all_passed and ok

    # --- 5. Deduped vs Steam total_count ---
    gap = abs(len(deduped_appids) - steam_total)
    ok = check(
        f"deduped count within ±{TOLERANCE} of Steam total_count",
        gap <= TOLERANCE or steam_total == 0,
        f"deduped={len(deduped_appids)}, steam={steam_total}, gap={gap}",
    )
    all_passed = all_passed and ok

    # --- 6. Invalid appids ---
    invalid = [a for a in deduped_appids if not a or not a.strip().isdigit()]
    ok = check(
        "no invalid appids in deduped CSV",
        len(invalid) == 0,
        f"{len(invalid)} invalid" if invalid else "all numeric",
    )
    all_passed = all_passed and ok
    if invalid:
        print(f"         Samples: {invalid[:5]}")

    # --- 7. Duplicate appids in deduped CSV ---
    dup_in_deduped = len(deduped_appids) - len(set(deduped_appids))
    ok = check(
        "no duplicate appids in deduped CSV",
        dup_in_deduped == 0,
        f"{dup_in_deduped} duplicates" if dup_in_deduped else "clean",
    )
    all_passed = all_passed and ok

    # --- 8. Random spot-check sample ---
    print(f"\n[SPOT CHECK]  {SAMPLE_N} random appids for manual verification:")
    sample = random.sample(deduped_appids, min(SAMPLE_N, len(deduped_appids)))
    for appid in sample:
        print(f"  https://store.steampowered.com/app/{appid}/")

    # --- Summary ---
    print("\n" + "=" * 55)
    if all_passed:
        print("  RESULT: ALL CHECKS PASSED")
        print(f"  {len(deduped_appids)} unique AO appids ready in ao_apps_deduped.csv")
        print("  Next step: Phase 2 (appdetails crawl)")
    else:
        print("  RESULT: SOME CHECKS FAILED — review output above")
    print("=" * 55)


if __name__ == "__main__":
    main()
