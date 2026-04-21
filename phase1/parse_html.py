"""
parse_html.py

Pure function: parse Steam Search results_html fragment
and extract (appid, name, url) records.

No I/O here — called by both crawl_search.py and merge_export.py.
"""

from bs4 import BeautifulSoup


def parse_results_html(html: str) -> list[dict]:
    """
    Parse the `results_html` value returned by the Steam search endpoint.

    Returns a list of dicts with keys: appid, name, url.
    Entries with invalid / missing appid are silently skipped.
    """
    if not html or not html.strip():
        return []

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("a.search_result_row")

    results = []
    for row in rows:
        appid = row.get("data-ds-appid", "").strip()

        # Skip non-app entries (bundles, packages carry comma-separated ids)
        if not appid or "," in appid or not appid.isdigit():
            continue

        title_el = row.select_one(".title")
        name = title_el.get_text(strip=True) if title_el else ""

        # Strip query string from URL so it stays clean
        raw_url = row.get("href", "")
        url = raw_url.split("?")[0].rstrip("/")

        results.append({
            "appid": appid,
            "name": name,
            "url": url,
        })

    return results
