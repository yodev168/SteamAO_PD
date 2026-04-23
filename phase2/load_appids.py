"""
load_appids.py

Helper: read ao_apps_deduped.csv and return a list of (appid, name) tuples.
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import DEDUPED_CSV


def load_appids() -> list[tuple[int, str]]:
    if not DEDUPED_CSV.exists():
        print(f"[ERROR] {DEDUPED_CSV} not found. Run phase1 first.")
        sys.exit(1)

    entries: list[tuple[int, str]] = []
    with open(DEDUPED_CSV, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            # Normalize headers to tolerate BOM/whitespace from edited CSV files.
            reader.fieldnames = [name.strip() for name in reader.fieldnames]

        for row in reader:
            normalized = {k.strip(): v for k, v in row.items() if k is not None}
            try:
                appid = int((normalized.get("appid") or "").strip())
                name = (normalized.get("name") or "").strip()
                entries.append((appid, name))
            except ValueError:
                continue

    if not entries:
        print(f"[ERROR] {DEDUPED_CSV} has no valid rows.")
        print("[HINT] Check CSV headers include: appid, name")
        sys.exit(1)

    return entries
