"""
fetch_store_html.py

HTML fallback fetcher: for appids where appdetails returned success:false
or is missing key fields (name / price / release_date), fetch the store
page using the phase1 cookie to bypass the age gate.

Only triggered for appids that need it — keeps cookie usage minimal.

Features:
- Identifies fallback candidates from raw/appdetails/
- Skips already-fetched HTML files (checkpoint / resume)
- Retries on HTTP 429 (wait 5 min) and 5xx (wait 30s, max 3 times)
- Detects expired / missing cookies and exits with clear message
- Writes per-entry log to crawl_log.jsonl

Run:
    cd phase2
    python fetch_store_html.py
"""

import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    COOKIES_FILE,
    LOG_FILE,
    MAX_RETRIES_5XX,
    MIN_VALID_HTML_BYTES,
    RAW_APPDETAILS_DIR,
    RAW_ERRORS_DIR,
    RAW_HTML_DIR,
    THROTTLE_HTML_CEIL,
    THROTTLE_HTML_MAX,
    THROTTLE_HTML_MIN,
    THROTTLE_RECOVER_EVERY,
    THROTTLE_RECOVER_STEP,
    THROTTLE_SHIFT_ON_429,
    SLEEP_ON_429,
    SLEEP_ON_5XX,
    STORE_PAGE_PARAMS,
    STORE_PAGE_URL,
    USER_AGENT,
)
from load_appids import load_appids


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_console_text(text: str) -> str:
    encoding = sys.stdout.encoding or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding, errors="replace")


class AdaptiveThrottle:
    def __init__(self, base_min: float, base_max: float, ceiling: float) -> None:
        self.base_min = base_min
        self.base_max = base_max
        self.cur_min = base_min
        self.cur_max = base_max
        self.ceiling = ceiling
        self.success_streak = 0

    def on_success(self) -> None:
        self.success_streak += 1
        if self.success_streak >= THROTTLE_RECOVER_EVERY:
            self.success_streak = 0
            self.cur_min = max(self.base_min, self.cur_min - THROTTLE_RECOVER_STEP)
            self.cur_max = max(self.base_max, self.cur_max - THROTTLE_RECOVER_STEP)

    def on_429(self) -> None:
        self.cur_min = min(self.ceiling, self.cur_min + THROTTLE_SHIFT_ON_429)
        self.cur_max = min(self.ceiling, self.cur_max + THROTTLE_SHIFT_ON_429)
        if self.cur_max < self.cur_min:
            self.cur_max = self.cur_min
        self.success_streak = 0

    def sleep(self) -> None:
        time.sleep(random.uniform(self.cur_min, self.cur_max))


def write_log(entry: dict) -> None:
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def html_path(appid: int) -> Path:
    return RAW_HTML_DIR / f"{appid}.html"


def error_path(appid: int) -> Path:
    return RAW_ERRORS_DIR / f"{appid}_html.txt"


def load_cookies() -> dict:
    if not COOKIES_FILE.exists():
        print(
            f"[ERROR] {COOKIES_FILE} not found.\n"
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


def is_cookie_error(html: str) -> bool:
    """Detect redirects to age-check or login pages."""
    if len(html) < MIN_VALID_HTML_BYTES:
        return True
    markers = ["agecheck", "login?redir", "steamsignin", "please log in"]
    lower = html.lower()
    return any(m in lower for m in markers)


def needs_fallback(appid: int) -> bool:
    """
    Returns True if this appid needs an HTML fallback.
    Conditions: no appdetails file, or success:false, or missing name/price/release_date.
    """
    path = RAW_APPDETAILS_DIR / f"{appid}.json"
    if not path.exists():
        return True

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return True

    if str(appid) in data:
        inner = data.get(str(appid), {})
    elif "tw" in data:
        inner = data.get("tw", {}).get(str(appid), {})
    else:
        inner = {}
    if not inner.get("success", False):
        return True

    game_data = inner.get("data", {})
    if not game_data:
        return True

    # Missing any critical field → fallback
    if not game_data.get("name"):
        return True
    if "price_overview" not in game_data and not game_data.get("is_free", False):
        return True
    if not game_data.get("release_date"):
        return True

    return False


def fetch_html(session: requests.Session, appid: int, throttle: AdaptiveThrottle) -> str | None:
    """
    Fetch the store page HTML for one appid using the cookie session.
    Returns HTML string or None on failure.
    Exits on cookie validation failure.
    """
    url = STORE_PAGE_URL.format(appid=appid)
    retries_5xx = 0

    while True:
        try:
            resp = session.get(url, params=STORE_PAGE_PARAMS, timeout=30)
        except requests.RequestException as exc:
            print(f"[WARN]  appid={appid} network error: {exc} — retrying in 30s")
            time.sleep(30)
            continue

        if resp.status_code == 429:
            throttle.on_429()
            print(
                f"[WARN]  appid={appid} HTTP 429 — waiting {SLEEP_ON_429}s..."
                f" (next_delay={throttle.cur_min:.1f}~{throttle.cur_max:.1f}s)"
            )
            time.sleep(SLEEP_ON_429)
            continue

        if resp.status_code >= 500:
            retries_5xx += 1
            if retries_5xx > MAX_RETRIES_5XX:
                print(f"[ERROR] appid={appid} HTTP {resp.status_code} after {MAX_RETRIES_5XX} retries — skipping")
                error_path(appid).write_text(resp.text, encoding="utf-8")
                return None
            print(f"[WARN]  appid={appid} HTTP {resp.status_code} — retry {retries_5xx}/{MAX_RETRIES_5XX} in {SLEEP_ON_5XX}s")
            time.sleep(SLEEP_ON_5XX)
            continue

        if resp.status_code == 404:
            print(f"[WARN]  appid={appid} HTTP 404 (delisted) — skipping")
            error_path(appid).write_text("HTTP 404", encoding="utf-8")
            return None

        if resp.status_code != 200:
            print(f"[WARN]  appid={appid} HTTP {resp.status_code} — skipping")
            error_path(appid).write_text(resp.text[:500], encoding="utf-8")
            return None

        html = resp.text

        if is_cookie_error(html):
            print(
                "\n[ERROR] Cookie validation failed.\n"
                "  Steam returned a login / age-check page instead of the store page.\n"
                "  Please re-export your cookies and update phase1/cookies.json.\n"
                "  Then re-run this script (already-saved HTML will be skipped)."
            )
            sys.exit(2)

        throttle.on_success()
        return html


def run() -> None:
    RAW_HTML_DIR.mkdir(parents=True, exist_ok=True)
    RAW_ERRORS_DIR.mkdir(parents=True, exist_ok=True)

    cookies = load_cookies()
    entries = load_appids()
    total = len(entries)

    # Find fallback candidates
    candidates = [(appid, name) for appid, name in entries if needs_fallback(appid)]
    print(f"[INFO]  {len(candidates)} / {total} appids need HTML fallback")

    if not candidates:
        print("[DONE]  No fallback needed — all appdetails are complete.")
        return

    session = requests.Session()
    session.cookies.update(cookies)
    session.headers.update({"User-Agent": USER_AGENT})
    throttle = AdaptiveThrottle(
        base_min=THROTTLE_HTML_MIN,
        base_max=THROTTLE_HTML_MAX,
        ceiling=THROTTLE_HTML_CEIL,
    )

    done = 0
    skipped = 0
    failed = 0
    total_candidates = len(candidates)

    print(f"[START] {now_iso()}  delay={throttle.cur_min:.1f}~{throttle.cur_max:.1f}s")

    for idx, (appid, name) in enumerate(candidates, 1):
        dest = html_path(appid)

        # Checkpoint: skip already-fetched
        if dest.exists() and dest.stat().st_size >= MIN_VALID_HTML_BYTES:
            skipped += 1
            if skipped <= 5 or skipped % 200 == 0:
                print(f"[CACHE] {idx}/{total_candidates}  appid={appid}")
            continue

        html = fetch_html(session, appid, throttle)

        if html is None:
            failed += 1
            status = "error"
        else:
            dest.write_text(html, encoding="utf-8")
            done += 1
            status = "ok"

        tag = "[OK  ]" if html else "[FAIL]"
        print(f"{tag} {idx}/{total_candidates}  appid={appid}  {safe_console_text(name[:40])}")

        write_log({
            "ts": now_iso(),
            "phase": "2_html_fallback",
            "appid": appid,
            "status": status,
            "delay_min_s": round(throttle.cur_min, 2),
            "delay_max_s": round(throttle.cur_max, 2),
        })

        throttle.sleep()

    print(f"\n[END]   {now_iso()}")
    print(f"        Candidates : {total_candidates}")
    print(f"        Fetched    : {done}")
    print(f"        Cached     : {skipped}")
    print(f"        Failed     : {failed}")
    print(f"  Next: python merge_master.py")


if __name__ == "__main__":
    run()
