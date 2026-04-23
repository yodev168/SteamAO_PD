"""
fetch_reviews.py

Fetch Steam review summary for all AO games using the public appreviews API.
Only the query_summary object is stored — no individual review content.

Features:
- Reads appids from phase1/ao_apps_deduped.csv
- Skips already-fetched files (checkpoint / resume)
- Retries on HTTP 429 (wait 5 min) and 5xx (wait 30s, max 3 times)
- Writes per-entry log to crawl_log.jsonl

Run:
    cd phase2
    python fetch_reviews.py
"""

import json
import queue
import random
import sys
import threading
import time
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    APPREVIEWS_PARAMS,
    APPREVIEWS_URL,
    LOG_FILE,
    MAX_RETRIES_5XX,
    MIN_VALID_JSON_BYTES,
    RAW_ERRORS_DIR,
    RAW_REVIEWS_DIR,
    REVIEWS_MAX_NETWORK_RETRIES,
    REVIEWS_NETWORK_RETRY_SLEEP,
    REVIEWS_REQUEST_TIMEOUT,
    REVIEWS_WORKERS,
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


class GlobalRateGate:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cooldown_until = 0.0

    def trigger_cooldown(self, seconds: float) -> None:
        next_until = time.time() + seconds
        with self._lock:
            self._cooldown_until = max(self._cooldown_until, next_until)

    def wait_if_needed(self) -> None:
        while True:
            with self._lock:
                wait_seconds = self._cooldown_until - time.time()
            if wait_seconds <= 0:
                return
            time.sleep(min(wait_seconds, 1.0))


class CrawlStats:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.done = 0
        self.skipped = 0
        self.failed = 0

    def add_done(self) -> None:
        with self._lock:
            self.done += 1

    def add_skipped(self) -> None:
        with self._lock:
            self.skipped += 1

    def add_failed(self) -> None:
        with self._lock:
            self.failed += 1

    def snapshot(self) -> tuple[int, int, int]:
        with self._lock:
            return self.done, self.skipped, self.failed


def write_log(entry: dict) -> None:
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def reviews_path(appid: int) -> Path:
    return RAW_REVIEWS_DIR / f"{appid}.json"


def error_path(appid: int) -> Path:
    return RAW_ERRORS_DIR / f"{appid}_reviews.txt"


def fetch_reviews(
    session: requests.Session,
    appid: int,
    throttle: AdaptiveThrottle,
    rate_gate: GlobalRateGate,
) -> dict | None:
    """
    Fetch review summary for one appid.
    Returns only the query_summary dict, or None on failure.
    """
    url = APPREVIEWS_URL.format(appid=appid)
    retries_5xx = 0
    retries_network = 0

    while True:
        rate_gate.wait_if_needed()
        try:
            resp = session.get(url, params=APPREVIEWS_PARAMS, timeout=REVIEWS_REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            retries_network += 1
            if retries_network > REVIEWS_MAX_NETWORK_RETRIES:
                print(
                    f"[ERROR] appid={appid} network error after "
                    f"{REVIEWS_MAX_NETWORK_RETRIES} retries — skipping"
                )
                error_path(appid).write_text(str(exc), encoding="utf-8")
                return None
            print(
                f"[WARN]  appid={appid} network error: {exc} — "
                f"retry {retries_network}/{REVIEWS_MAX_NETWORK_RETRIES} in {REVIEWS_NETWORK_RETRY_SLEEP}s"
            )
            time.sleep(REVIEWS_NETWORK_RETRY_SLEEP)
            continue

        retries_network = 0

        if resp.status_code == 429:
            throttle.on_429()
            rate_gate.trigger_cooldown(SLEEP_ON_429)
            print(
                f"[WARN]  appid={appid} HTTP 429 — global cooldown {SLEEP_ON_429}s..."
                f" (next_delay={throttle.cur_min:.1f}~{throttle.cur_max:.1f}s)"
            )
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

        if resp.status_code != 200:
            print(f"[WARN]  appid={appid} HTTP {resp.status_code} — skipping")
            error_path(appid).write_text(resp.text, encoding="utf-8")
            return None

        raw_text = resp.text
        if len(raw_text) < MIN_VALID_JSON_BYTES:
            print(f"[WARN]  appid={appid} response too short ({len(raw_text)} bytes) — skipping")
            error_path(appid).write_text(raw_text, encoding="utf-8")
            return None

        try:
            data = resp.json()
        except json.JSONDecodeError as exc:
            print(f"[WARN]  appid={appid} JSON decode error: {exc} — skipping")
            error_path(appid).write_text(raw_text, encoding="utf-8")
            return None

        if data.get("success") != 1:
            print(f"[WARN]  appid={appid} success!=1 — skipping")
            error_path(appid).write_text(raw_text, encoding="utf-8")
            return None

        # Only store the summary — no user data
        throttle.on_success()
        summary = data.get("query_summary", {})
        return {
            "appid": appid,
            "fetched_at": now_iso(),
            "query_summary": summary,
        }


def worker_loop(
    worker_id: int,
    total: int,
    task_queue: queue.Queue[tuple[int, int, str]],
    stats: CrawlStats,
    rate_gate: GlobalRateGate,
    io_lock: threading.Lock,
) -> None:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    throttle = AdaptiveThrottle(
        base_min=THROTTLE_API_MIN,
        base_max=THROTTLE_API_MAX,
        ceiling=THROTTLE_API_CEIL,
    )

    while True:
        try:
            idx, appid, name = task_queue.get_nowait()
        except queue.Empty:
            return

        dest = reviews_path(appid)

        if dest.exists() and dest.stat().st_size >= MIN_VALID_JSON_BYTES:
            stats.add_skipped()
            if idx <= 5 or idx % 500 == 0:
                with io_lock:
                    print(f"[CACHE] {idx}/{total}  appid={appid}")
            continue

        result = fetch_reviews(session, appid, throttle, rate_gate)

        if result is None:
            stats.add_failed()
            status = "error"
            total_reviews = -1
        else:
            dest.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            stats.add_done()
            status = "ok"
            total_reviews = result["query_summary"].get("total_reviews", 0)

        tag = f"[OK  reviews={total_reviews}]" if result else "[FAIL]"
        with io_lock:
            print(f"[W{worker_id}] {tag} {idx}/{total}  appid={appid}  {safe_console_text(name[:40])}")

        with io_lock:
            write_log({
                "ts": now_iso(),
                "phase": "2_reviews",
                "appid": appid,
                "status": status,
                "total_reviews": total_reviews,
                "delay_min_s": round(throttle.cur_min, 2),
                "delay_max_s": round(throttle.cur_max, 2),
                "worker": worker_id,
            })

        throttle.sleep()


def run(workers_override: int | None = None) -> None:
    RAW_REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    RAW_ERRORS_DIR.mkdir(parents=True, exist_ok=True)

    entries = load_appids()
    total = len(entries)
    task_queue: queue.Queue[tuple[int, int, str]] = queue.Queue()
    for idx, (appid, name) in enumerate(entries, 1):
        task_queue.put((idx, appid, name))

    stats = CrawlStats()
    rate_gate = GlobalRateGate()
    io_lock = threading.Lock()
    workers = max(1, workers_override if workers_override is not None else REVIEWS_WORKERS)

    print(
        f"[START] {now_iso()}  total appids: {total}  workers={workers}  "
        f"delay={THROTTLE_API_MIN:.1f}~{THROTTLE_API_MAX:.1f}s"
    )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(worker_loop, wid, total, task_queue, stats, rate_gate, io_lock)
            for wid in range(1, workers + 1)
        ]
        for future in futures:
            future.result()

    print(f"\n[END]   {now_iso()}")
    done, skipped, failed = stats.snapshot()
    print(f"        Total   : {total}")
    print(f"        Fetched : {done}")
    print(f"        Cached  : {skipped}")
    print(f"        Failed  : {failed}")
    print(f"  Next: python fetch_store_html.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch Steam review summaries")
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help=f"Number of concurrent workers (default: {REVIEWS_WORKERS})",
    )
    args = parser.parse_args()
    run(workers_override=args.workers)
