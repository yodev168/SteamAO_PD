"""
fetch_appdetails.py

Fetch Steam appdetails for all AO games using the public API (no cookie needed).
Results are saved per-appid to raw/appdetails/<appid>.json.

Features:
- Reads appids from phase1/ao_apps_deduped.csv
- Smart checkpoint: skips files that already contain the new enriched fields
  (checks for 'developers' key in data); re-fetches old format files automatically
- tw and us requests are sent sequentially (tw first, then us after throttle sleep)
- Retries on HTTP 429 (wait 5 min) and 5xx (wait 30s, max 3 times)
- Writes per-entry log to crawl_log.jsonl
- Records failures to raw/errors/<appid>.txt

Run:
    cd phase2
    python fetch_appdetails.py
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
    APPDETAILS_PARAMS,
    APPDETAILS_URL,
    LOG_FILE,
    MAX_RETRIES_5XX,
    MIN_VALID_JSON_BYTES,
    RAW_APPDETAILS_DIR,
    RAW_ERRORS_DIR,
    THROTTLE_API_CEIL,
    THROTTLE_API_MAX,
    THROTTLE_API_MIN,
    THROTTLE_RECOVER_EVERY,
    THROTTLE_RECOVER_STEP,
    THROTTLE_SHIFT_ON_429,
    SLEEP_ON_429,
    SLEEP_ON_5XX,
    USER_AGENT,
)
from load_appids import load_appids


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_console_text(text: str) -> str:
    encoding = sys.stdout.encoding or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding, errors="replace")


class AdaptiveThrottle:
    def __init__(
        self,
        base_min: float,
        base_max: float,
        ceiling: float,
    ) -> None:
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


def appdetails_path(appid: int) -> Path:
    return RAW_APPDETAILS_DIR / f"{appid}.json"


def error_path(appid: int, stage: str) -> Path:
    return RAW_ERRORS_DIR / f"{appid}_{stage}.txt"


def is_already_enriched(appid: int, path: Path) -> bool:
    """
    Return True if the file already contains enriched data (has 'developers' key).
    Old-format files (missing developers) return False and will be re-fetched.
    Known-bad files (success=false) return True to avoid infinite retry.
    """
    if not path.exists() or path.stat().st_size < MIN_VALID_JSON_BYTES:
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if "tw" in data:
            tw_inner = data["tw"].get(str(appid), {})
        else:
            tw_inner = data.get(str(appid), {})
        if not tw_inner.get("success", False):
            return True  # known-bad response, no point retrying
        game = tw_inner.get("data") or {}
        return "developers" in game
    except Exception:
        return False


def fetch_one(
    session: requests.Session,
    appid: int,
    cc: str,
    lang: str,
    throttle: AdaptiveThrottle,
) -> dict | None:
    """
    Fetch appdetails for one appid + cc.
    Returns the raw JSON dict or None on failure.
    Handles 429 and 5xx with retries.
    """
    params = {**APPDETAILS_PARAMS, "cc": cc, "l": lang, "appids": str(appid)}
    retries_5xx = 0

    while True:
        try:
            resp = session.get(APPDETAILS_URL, params=params, timeout=30)
        except requests.RequestException as exc:
            print(f"[WARN]  appid={appid} [{cc}] network error: {exc} — retrying in 30s")
            time.sleep(30)
            continue

        if resp.status_code == 429:
            throttle.on_429()
            print(
                f"[WARN]  appid={appid} [{cc}] HTTP 429 — waiting {SLEEP_ON_429}s..."
                f" (next_delay={throttle.cur_min:.1f}~{throttle.cur_max:.1f}s)"
            )
            time.sleep(SLEEP_ON_429)
            continue

        if resp.status_code >= 500:
            retries_5xx += 1
            if retries_5xx > MAX_RETRIES_5XX:
                print(f"[ERROR] appid={appid} [{cc}] HTTP {resp.status_code} after {MAX_RETRIES_5XX} retries — skipping")
                error_path(appid, f"appdetails_{cc}").write_text(resp.text, encoding="utf-8")
                return None
            print(f"[WARN]  appid={appid} [{cc}] HTTP {resp.status_code} — retry {retries_5xx}/{MAX_RETRIES_5XX} in {SLEEP_ON_5XX}s")
            time.sleep(SLEEP_ON_5XX)
            continue

        if resp.status_code != 200:
            print(f"[WARN]  appid={appid} [{cc}] HTTP {resp.status_code} — skipping")
            error_path(appid, f"appdetails_{cc}").write_text(resp.text, encoding="utf-8")
            return None

        raw_text = resp.text
        if len(raw_text) < MIN_VALID_JSON_BYTES:
            print(f"[WARN]  appid={appid} [{cc}] response too short ({len(raw_text)} bytes) — skipping")
            error_path(appid, f"appdetails_{cc}").write_text(raw_text, encoding="utf-8")
            return None

        try:
            data = resp.json()
        except json.JSONDecodeError as exc:
            print(f"[WARN]  appid={appid} [{cc}] JSON decode error: {exc} — skipping")
            error_path(appid, f"appdetails_{cc}").write_text(raw_text, encoding="utf-8")
            return None

        throttle.on_success()
        return data


def run() -> None:
    RAW_APPDETAILS_DIR.mkdir(parents=True, exist_ok=True)
    RAW_ERRORS_DIR.mkdir(parents=True, exist_ok=True)

    entries = load_appids()
    total = len(entries)

    session_tw = requests.Session()
    session_tw.headers.update({"User-Agent": USER_AGENT})
    session_us = session_tw

    throttle = AdaptiveThrottle(
        base_min=THROTTLE_API_MIN,
        base_max=THROTTLE_API_MAX,
        ceiling=THROTTLE_API_CEIL,
    )

    done = 0
    skipped = 0
    failed = 0

    print(
        f"[START] {now_iso()}  total appids: {total}  "
        f"delay={throttle.cur_min:.1f}~{throttle.cur_max:.1f}s  tw→us sequential"
    )

    for idx, (appid, name) in enumerate(entries, 1):
        dest = appdetails_path(appid)

        # Smart checkpoint: skip only if already enriched (has 'developers' key)
        if is_already_enriched(appid, dest):
            skipped += 1
            if skipped <= 5 or skipped % 500 == 0:
                print(f"[CACHE] {idx}/{total}  appid={appid}")
            continue

        # Fetch tw first, then us sequentially to avoid triggering 429
        tw_data = fetch_one(session_tw, appid, "tw", "tchinese", throttle)
        throttle.sleep()
        us_data = fetch_one(session_us, appid, "us", "english", throttle) if tw_data is not None else None

        if tw_data is None:
            failed += 1
            status = "error"
            success = False
            has_us = False
        else:
            inner = tw_data.get(str(appid), {})
            success = inner.get("success", False)
            us_inner = (us_data or {}).get(str(appid), {})
            has_us = us_inner.get("success", False)
            payload = {
                "tw": tw_data,
                "us": us_data,
                "fetched_at": now_iso(),
            }
            dest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            done += 1
            status = "ok" if success else "no_data"

        tag = f"[{'OK' if success else 'NO_DATA'}]" if tw_data is not None else "[FAIL]"
        print(f"{tag} {idx}/{total}  appid={appid}  {safe_console_text(name[:40])}")

        write_log({
            "ts": now_iso(),
            "phase": "2_appdetails",
            "appid": appid,
            "status": status,
            "success": success,
            "has_us": has_us,
            "delay_min_s": round(throttle.cur_min, 2),
            "delay_max_s": round(throttle.cur_max, 2),
        })

        throttle.sleep()

    print(f"\n[END]   {now_iso()}")
    print(f"        Total   : {total}")
    print(f"        Fetched : {done}")
    print(f"        Cached  : {skipped}")
    print(f"        Failed  : {failed}")
    print(f"  Next: python fetch_reviews.py")


if __name__ == "__main__":
    run()
