"""
crawl_search.py

Crawl all AO game appids from the Steam Search endpoint.

Features:
- Pagination via `start` parameter (0, 50, 100, ...)
- Resumes from checkpoint: skips raw files that already exist
- Retries on HTTP 429 (wait 5 min) and 5xx (wait 30s, max 3 times)
- Detects expired / missing cookies and exits with clear message
- Writes JSONL log to crawl_log.jsonl and prints progress to stdout
- Output: raw/search_start_{start}.json for every page

Run:
    cd phase1
    python crawl_search.py
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# Allow running from any working directory
sys.path.insert(0, str(Path(__file__).parent))
from config import (
    COOKIES_FILE,
    LOG_FILE,
    MAX_RETRIES_5XX,
    MIN_VALID_RESPONSE_BYTES,
    RAW_DIR,
    SEARCH_PARAMS,
    SEARCH_URL,
    SLEEP_BETWEEN_REQUESTS,
    SLEEP_ON_429,
    SLEEP_ON_5XX,
    USER_AGENT,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_cookies() -> dict:
    if not COOKIES_FILE.exists():
        print(
            f"[ERROR] cookies.json not found at {COOKIES_FILE}\n"
            "  Please follow phase1/README.md to export your Steam cookies first."
        )
        sys.exit(1)
    with open(COOKIES_FILE, encoding="utf-8") as f:
        cookies = json.load(f)
    required = {"sessionid", "steamLoginSecure"}
    missing = required - cookies.keys()
    if missing:
        print(f"[ERROR] cookies.json is missing keys: {missing}")
        sys.exit(1)
    return cookies


def write_log(entry: dict) -> None:
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def is_cookie_error(raw_text: str) -> bool:
    """Detect redirects to age-check or login pages."""
    if len(raw_text) < MIN_VALID_RESPONSE_BYTES:
        return True
    markers = ["agecheck", "login?redir", "steamsignin", "please log in"]
    lower = raw_text.lower()
    return any(m in lower for m in markers)


def raw_path(start: int) -> Path:
    return RAW_DIR / f"search_start_{start}.json"


def error_path(start: int) -> Path:
    return RAW_DIR / f"error_start_{start}.txt"


# ---------------------------------------------------------------------------
# Core request with retry
# ---------------------------------------------------------------------------

def fetch_page(session: requests.Session, start: int) -> dict | None:
    """
    Fetch one page of search results.
    Returns parsed JSON dict, or None if the response was empty / error.
    Handles 429 and 5xx with appropriate sleeps.
    On cookie error: exits the process.
    """
    params = {**SEARCH_PARAMS, "start": start}
    retries_5xx = 0

    while True:
        try:
            resp = session.get(SEARCH_URL, params=params, timeout=30)
        except requests.RequestException as exc:
            print(f"[WARN]  start={start} network error: {exc} — retrying in 30s")
            time.sleep(30)
            continue

        if resp.status_code == 429:
            print(f"[WARN]  start={start} HTTP 429 — waiting {SLEEP_ON_429}s...")
            time.sleep(SLEEP_ON_429)
            continue

        if resp.status_code >= 500:
            retries_5xx += 1
            if retries_5xx > MAX_RETRIES_5XX:
                print(f"[ERROR] start={start} HTTP {resp.status_code} after {MAX_RETRIES_5XX} retries — skipping")
                error_path(start).write_text(resp.text, encoding="utf-8")
                return None
            print(f"[WARN]  start={start} HTTP {resp.status_code} — retry {retries_5xx}/{MAX_RETRIES_5XX} in {SLEEP_ON_5XX}s")
            time.sleep(SLEEP_ON_5XX)
            continue

        if resp.status_code != 200:
            print(f"[WARN]  start={start} HTTP {resp.status_code} — skipping")
            error_path(start).write_text(resp.text, encoding="utf-8")
            return None

        raw_text = resp.text

        if is_cookie_error(raw_text):
            print(
                "\n[ERROR] Cookie validation failed.\n"
                "  Steam returned a login / age-check page instead of results.\n"
                "  Please re-export your cookies and update phase1/cookies.json.\n"
                "  Then re-run this script (already-saved pages will be skipped)."
            )
            sys.exit(2)

        try:
            data = resp.json()
        except json.JSONDecodeError as exc:
            print(f"[WARN]  start={start} JSON decode error: {exc} — saving raw and skipping")
            error_path(start).write_text(raw_text, encoding="utf-8")
            return None

        return data


# ---------------------------------------------------------------------------
# Main crawl loop
# ---------------------------------------------------------------------------

def crawl() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cookies = load_cookies()

    session = requests.Session()
    session.cookies.update(cookies)
    session.headers.update({"User-Agent": USER_AGENT})

    start = 0
    total_count = None
    total_seen = 0

    print(f"[START] {now_iso()}  target URL: {SEARCH_URL}")

    while True:
        dest = raw_path(start)

        # --- Checkpoint: skip already-crawled pages ---
        if dest.exists() and dest.stat().st_size > MIN_VALID_RESPONSE_BYTES:
            # Read total_count from cache to know when to stop
            with open(dest, encoding="utf-8") as f:
                cached = json.load(f)
            got = len(cached.get("results_html", "")) > 10
            if total_count is None:
                total_count = cached.get("total_count", 0)

            # Rough count from cached page (just for display)
            from parse_html import parse_results_html
            cached_entries = parse_results_html(cached.get("results_html", ""))
            total_seen += len(cached_entries)

            tag = f"total={total_seen}/{total_count}" if total_count else ""
            print(f"[CACHE] start={start:<6} {tag}")

            if not cached.get("results_html", "").strip():
                print("[DONE]  Cached empty page — all pages already fetched")
                break
            start += SEARCH_PARAMS["count"]
            continue

        # --- Fetch ---
        data = fetch_page(session, start)

        if data is None:
            start += SEARCH_PARAMS["count"]
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            continue

        results_html = data.get("results_html", "")
        if total_count is None:
            total_count = data.get("total_count", 0)

        # Parse to count entries (for logging only — don't discard raw)
        from parse_html import parse_results_html
        entries = parse_results_html(results_html)
        got = len(entries)
        total_seen += got

        # Save raw response
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        # Log
        log_entry = {
            "ts": now_iso(),
            "phase": "1a",
            "start": start,
            "got": got,
            "total_seen": total_seen,
            "target": total_count,
            "status": "ok",
        }
        write_log(log_entry)

        tag = f"total={total_seen}/{total_count}" if total_count else f"got={got}"
        done_tag = " DONE" if (not results_html.strip() or (total_count and start + got >= total_count)) else ""
        print(f"[FETCH] start={start:<6} got={got:<4} {tag}{done_tag}")

        # --- Stop conditions ---
        if not results_html.strip():
            print("[DONE]  results_html is empty — reached end of results")
            break
        if total_count and start + SEARCH_PARAMS["count"] >= total_count + SEARCH_PARAMS["count"]:
            print("[DONE]  start exceeded total_count — all pages fetched")
            break

        start += SEARCH_PARAMS["count"]
        time.sleep(SLEEP_BETWEEN_REQUESTS)

    print(f"\n[END]   {now_iso()}")
    print(f"        Pages saved: {len(list(RAW_DIR.glob('search_start_*.json')))}")
    print(f"        Run 'python merge_export.py' next")


if __name__ == "__main__":
    crawl()
