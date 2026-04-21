"""
merge_export.py

Scan raw/search_start_*.json, parse HTML fragments, and export:
  - ao_apps_raw.csv    (all records including duplicates)
  - ao_apps_deduped.csv (deduplicated by appid, first-seen wins)

Run after crawl_search.py:
    cd phase1
    python merge_export.py
"""

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import DEDUPED_CSV, RAW_CSV, RAW_DIR
from parse_html import parse_results_html


def file_mtime_iso(path: Path) -> str:
    """Return file modification time as ISO 8601 UTC string."""
    mtime = path.stat().st_mtime
    return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iter_raw_files() -> list[Path]:
    """Return raw page files sorted by start index (numeric order)."""
    files = list(RAW_DIR.glob("search_start_*.json"))
    files.sort(key=lambda p: int(p.stem.split("_")[-1]))
    return files


def load_all_records() -> tuple[list[dict], set[int]]:
    """
    Parse every raw file and return:
      - all_records: flat list (may contain duplicates)
      - total_counts: set of total_count values seen across all pages
    """
    raw_files = iter_raw_files()
    if not raw_files:
        print(f"[ERROR] No raw files found in {RAW_DIR}")
        print("  Run 'python crawl_search.py' first.")
        sys.exit(1)

    all_records: list[dict] = []
    total_counts: set[int] = set()

    for path in raw_files:
        discovered_at = file_mtime_iso(path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        tc = data.get("total_count")
        if tc:
            total_counts.add(tc)

        entries = parse_results_html(data.get("results_html", ""))
        for entry in entries:
            all_records.append({
                "appid": entry["appid"],
                "name": entry["name"],
                "url": entry["url"],
                "source_tab": "search",
                "discovered_at": discovered_at,
            })

    return all_records, total_counts


def write_raw_csv(records: list[dict]) -> None:
    fieldnames = ["appid", "name", "url", "source_tab", "discovered_at"]
    with open(RAW_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    print(f"[CSV]   ao_apps_raw.csv     {len(records):>6} rows  -> {RAW_CSV}")


def write_deduped_csv(records: list[dict]) -> dict:
    """
    Deduplicate by appid (first-seen wins) and write ao_apps_deduped.csv.
    Returns the dedup dict for downstream use.
    """
    seen: dict[str, dict] = {}
    for rec in records:
        appid = rec["appid"]
        if appid not in seen:
            seen[appid] = {
                "appid": appid,
                "name": rec["name"],
                "url": rec["url"],
                "source_search": 1,
                # Placeholders for Phase 1b (Hub sources)
                "source_hub_all": 0,
                "source_hub_upcoming": 0,
                "first_seen_at": rec["discovered_at"],
            }

    fieldnames = [
        "appid", "name", "url",
        "source_search", "source_hub_all", "source_hub_upcoming",
        "first_seen_at",
    ]
    with open(DEDUPED_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(seen.values())

    print(f"[CSV]   ao_apps_deduped.csv {len(seen):>6} rows  -> {DEDUPED_CSV}")
    return seen


def main() -> None:
    print(f"[START] Scanning {RAW_DIR} ...")

    all_records, total_counts = load_all_records()

    write_raw_csv(all_records)
    seen = write_deduped_csv(all_records)

    duplicates = len(all_records) - len(seen)
    print(f"\n[SUMMARY]")
    print(f"  Raw pages parsed  : {len(iter_raw_files())}")
    print(f"  Raw records       : {len(all_records)}")
    print(f"  Duplicates removed: {duplicates}")
    print(f"  Deduped appids    : {len(seen)}")
    if total_counts:
        print(f"  Steam total_count : {total_counts}")
    print(f"\n  Run 'python sanity_check.py' to validate.")


if __name__ == "__main__":
    main()
