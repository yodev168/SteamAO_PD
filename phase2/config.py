from pathlib import Path

# --- Paths ---
BASE_DIR = Path(__file__).parent
PHASE1_DIR = BASE_DIR.parent / "phase1"

RAW_DIR = BASE_DIR / "raw"
RAW_APPDETAILS_DIR = RAW_DIR / "appdetails"
RAW_REVIEWS_DIR = RAW_DIR / "reviews"
RAW_HTML_DIR = RAW_DIR / "html"
RAW_ERRORS_DIR = RAW_DIR / "errors"

DEDUPED_CSV = PHASE1_DIR / "ao_apps_deduped.csv"
COOKIES_FILE = PHASE1_DIR / "cookies.json"
LOG_FILE = BASE_DIR / "crawl_log.jsonl"
MASTER_CSV = BASE_DIR / "ao_games_master.csv"
MISSING_REPORT_CSV = BASE_DIR / "missing_report.csv"

# --- Endpoints ---
APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"
APPREVIEWS_URL = "https://store.steampowered.com/appreviews/{appid}"
STORE_PAGE_URL = "https://store.steampowered.com/app/{appid}/"

# --- appdetails params ---
APPDETAILS_PARAMS = {
    "cc": "tw",
    "l": "tchinese",
    "filters": "basic,price_overview,release_date,developers,publishers,genres,categories",
}

# --- appreviews params ---
APPREVIEWS_PARAMS = {
    "json": "1",
    "language": "all",
    "purchase_type": "all",
    "num_per_page": "0",
}

# --- store HTML params ---
STORE_PAGE_PARAMS = {
    "cc": "tw",
    "l": "tchinese",
}

# --- Request ---
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# --- Timing ---
SLEEP_ON_429 = 300              # 5 minutes
SLEEP_ON_5XX = 30               # seconds before retry
MAX_RETRIES_5XX = 3

# --- reviews crawler tuning ---
# Keep this small to avoid Steam rate limit spikes.
REVIEWS_WORKERS = 3
REVIEWS_REQUEST_TIMEOUT = 30
REVIEWS_MAX_NETWORK_RETRIES = 5
REVIEWS_NETWORK_RETRY_SLEEP = 10

# --- Adaptive random throttle ---
# Use randomized delays proactively, then shift the whole range on 429.
THROTTLE_API_MIN = 2.5
THROTTLE_API_MAX = 4.0
THROTTLE_HTML_MIN = 2.3
THROTTLE_HTML_MAX = 3.8
THROTTLE_API_CEIL = 10.0
THROTTLE_HTML_CEIL = 10.0
THROTTLE_SHIFT_ON_429 = 0.5
THROTTLE_RECOVER_EVERY = 20      # successful requests needed before range step-down
THROTTLE_RECOVER_STEP = 0.2

# --- Sanity ---
MIN_VALID_JSON_BYTES = 50
MIN_VALID_HTML_BYTES = 5000
