"""
sanity_check.py

Validate ao_games_master.csv completeness and produce missing_report.csv.

Checks:
  1. Row count matches phase1 deduped count
  2. name coverage >= 99%
  3. price_twd_original coverage >= 90% (excludes free + coming_soon)
  4. price_usd_original coverage report (optional)
  5. release_date coverage >= 95%
  6. review_count coverage >= 99% (appreviews almost never fails)
  7. Produces missing_report.csv listing all appids with any null critical field

Run:
    cd phase2
    python sanity_check.py
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import MASTER_CSV, MISSING_REPORT_CSV
from load_appids import load_appids

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
WARN = "\033[33mWARN\033[0m"


def safe_console_text(text: str) -> str:
    encoding = sys.stdout.encoding or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding, errors="replace")


def pct(n: int, total: int) -> str:
    return f"{n}/{total} ({100 * n / total:.1f}%)" if total else "0/0"


def run() -> None:
    if not MASTER_CSV.exists():
        print(f"[ERROR] {MASTER_CSV} not found. Run merge_master.py first.")
        sys.exit(1)

    with open(MASTER_CSV, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    total = len(rows)
    phase1_entries = load_appids()
    expected = len(phase1_entries)
    phase1_appids = {appid for appid, _ in phase1_entries}

    all_passed = True

    print("=" * 60)
    print("  Phase 2 Sanity Check")
    print("=" * 60)

    # --- Check 1: row count ---
    tag = PASS if total == expected else FAIL
    if total != expected:
        all_passed = False
    print(f"[{tag}] Row count: {total} (expected {expected})")

    # --- Check 2: name coverage ---
    has_name = sum(1 for r in rows if r.get("name", "").strip())
    name_pct = has_name / total if total else 0
    tag = PASS if name_pct >= 0.99 else (WARN if name_pct >= 0.95 else FAIL)
    if name_pct < 0.95:
        all_passed = False
    print(f"[{tag}] name coverage      : {pct(has_name, total)}")

    # --- Check 3: TWD original price coverage (non-free, non-coming-soon) ---
    paid_rows = [r for r in rows if r.get("is_free", "").lower() not in ("true", "1") and r.get("coming_soon", "").lower() not in ("true", "1")]
    has_twd = sum(1 for r in paid_rows if r.get("price_twd_original", "") not in ("", "None", None))
    twd_pct = has_twd / len(paid_rows) if paid_rows else 1.0
    tag = PASS if twd_pct >= 0.90 else WARN
    print(f"[{tag}] price_twd_original : {pct(has_twd, len(paid_rows))} (paid non-upcoming)")

    # --- Check 4: USD original price coverage (informational) ---
    has_usd = sum(1 for r in paid_rows if r.get("price_usd_original", "") not in ("", "None", None))
    usd_pct = has_usd / len(paid_rows) if paid_rows else 1.0
    tag = PASS if usd_pct >= 0.80 else WARN
    print(f"[{tag}] price_usd_original : {pct(has_usd, len(paid_rows))} (paid non-upcoming)")

    # --- Check 5: release_date coverage ---
    has_date = sum(1 for r in rows if r.get("release_date", "") not in ("", "None", None))
    date_pct = has_date / total if total else 0
    tag = PASS if date_pct >= 0.95 else WARN
    print(f"[{tag}] release_date cover : {pct(has_date, total)}")

    # --- Check 6: review_count coverage ---
    has_review = sum(1 for r in rows if r.get("review_count", "0") not in ("", "None", None, "0"))
    review_pct = has_review / total if total else 0
    tag = PASS if review_pct >= 0.99 else WARN
    print(f"[{tag}] review_count cover : {pct(has_review, total)}")

    # --- Check 7: appids present ---
    master_appids = {int(r["appid"]) for r in rows if r.get("appid", "").isdigit()}
    missing_from_master = phase1_appids - master_appids
    extra_in_master = master_appids - phase1_appids
    tag = PASS if not missing_from_master else FAIL
    if missing_from_master:
        all_passed = False
    print(f"[{tag}] appids from phase1 in master: {pct(len(phase1_appids) - len(missing_from_master), len(phase1_appids))}")
    if extra_in_master:
        print(f"[{WARN}] {len(extra_in_master)} extra appids in master not in phase1 deduped")

    # --- Source distribution ---
    n_appdetails = sum(1 for r in rows if r.get("source_appdetails", "").lower() in ("true", "1"))
    n_html = sum(1 for r in rows if r.get("source_html_fallback", "").lower() in ("true", "1"))
    n_none = total - n_appdetails - n_html
    print(f"\n  Source breakdown:")
    print(f"    appdetails only  : {pct(n_appdetails, total)}")
    print(f"    HTML fallback    : {pct(n_html, total)}")
    print(f"    no source data   : {pct(n_none, total)}")

    # --- Write missing_report.csv ---
    critical_fields = ["name", "price_twd_original", "release_date", "review_count"]
    missing_rows = []
    for r in rows:
        missing = [f for f in critical_fields if r.get(f, "") in ("", "None", None, "0")]
        if missing or int(r.get("appid", 0)) in missing_from_master:
            missing_rows.append({
                "appid": r.get("appid", ""),
                "name": r.get("name", ""),
                "missing_fields": ",".join(missing),
                "source_appdetails": r.get("source_appdetails", ""),
                "source_html_fallback": r.get("source_html_fallback", ""),
            })

    with open(MISSING_REPORT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["appid", "name", "missing_fields", "source_appdetails", "source_html_fallback"])
        writer.writeheader()
        writer.writerows(missing_rows)

    print(f"\n  missing_report.csv : {len(missing_rows)} rows → {MISSING_REPORT_CSV}")

    print("=" * 60)
    if all_passed:
        print(safe_console_text("  ✔ ALL CHECKS PASSED"))
    else:
        print(safe_console_text("  ✘ SOME CHECKS FAILED — review output above and missing_report.csv"))
    print("=" * 60)


if __name__ == "__main__":
    run()
