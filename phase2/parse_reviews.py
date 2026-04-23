"""
parse_reviews.py

Parse a raw reviews JSON file (query_summary only) into master review fields.
"""

import json
from pathlib import Path
from typing import Any


def parse_reviews(appid: int, path: Path) -> dict[str, Any] | None:
    """
    Read raw/reviews/<appid>.json and return review summary fields, or None on failure.

    Returned keys:
        appid, review_count, review_positive, review_negative,
        review_score, review_score_desc
    """
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    summary = data.get("query_summary", {})
    if not summary:
        return None

    review_positive: int = summary.get("total_positive", 0)
    review_negative: int = summary.get("total_negative", 0)
    review_count: int = summary.get("total_reviews", 0)

    total_voted = review_positive + review_negative
    positive_ratio: float | None = (
        round(review_positive / total_voted, 4) if total_voted > 0 else None
    )
    has_reviews: bool = review_count > 0

    return {
        "appid": appid,
        "review_count": review_count,
        "review_positive": review_positive,
        "review_negative": review_negative,
        "review_score": summary.get("review_score", 0),
        "review_score_desc": summary.get("review_score_desc", ""),
        "positive_ratio": positive_ratio,
        "has_reviews": has_reviews,
    }
