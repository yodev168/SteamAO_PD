from pathlib import Path

# --- Paths ---
BASE_DIR = Path(__file__).parent
RAW_DIR = BASE_DIR / "raw"
COOKIES_FILE = BASE_DIR / "cookies.json"
LOG_FILE = BASE_DIR / "crawl_log.jsonl"
RAW_CSV = BASE_DIR / "ao_apps_raw.csv"
DEDUPED_CSV = BASE_DIR / "ao_apps_deduped.csv"

# --- Endpoint ---
SEARCH_URL = "https://store.steampowered.com/search/results/"

SEARCH_PARAMS = {
    "query": "",
    "count": 50,
    "tags": "12095,24904",
    "category1": "998",
    "hidef2p": "1",
    "ndl": "1",
    "infinite": "1",
}

# --- Request ---
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# --- Timing ---
SLEEP_BETWEEN_REQUESTS = 1.2   # seconds between normal requests
SLEEP_ON_429 = 300             # seconds to wait after HTTP 429
SLEEP_ON_5XX = 30              # seconds to wait after HTTP 5xx
MAX_RETRIES_5XX = 3

# --- Sanity ---
MIN_VALID_RESPONSE_BYTES = 500  # responses shorter than this = likely cookie error
