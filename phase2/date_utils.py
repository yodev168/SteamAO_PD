"""Helpers for normalizing release date text into non-Chinese output."""

from __future__ import annotations

import re
from datetime import datetime

_CN_YMD_RE = re.compile(r"^\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?\s*$")
_CN_YM_RE = re.compile(r"^\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*$")
_NUMERIC_YMD_RE = re.compile(r"^\s*(\d{4})[./-](\d{1,2})[./-](\d{1,2})\s*$")
_NUMERIC_YM_RE = re.compile(r"^\s*(\d{4})[./-](\d{1,2})\s*$")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")

_COMING_SOON_HINTS = (
    "coming soon",
    "to be announced",
    "tba",
    "即將推出",
    "即将推出",
    "敬請期待",
    "敬请期待",
)

_EN_DATE_FORMATS = (
    "%b %d, %Y",
    "%B %d, %Y",
    "%d %b, %Y",
    "%d %B, %Y",
)


def _is_coming_soon(text: str) -> bool:
    lower_text = text.lower()
    for hint in _COMING_SOON_HINTS:
        if hint in lower_text or hint in text:
            return True
    return False


def normalize_release_date(raw: str | None) -> str | None:
    """Normalize raw release date to non-Chinese text."""
    if raw is None:
        return None

    text = re.sub(r"\s+", " ", str(raw)).strip()
    if not text:
        return None

    if _is_coming_soon(text):
        return "Coming Soon"

    m = _CN_YMD_RE.match(text)
    if m:
        year, month, day = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return f"{year:04d}-{month:02d}-{day:02d}"

    m = _CN_YM_RE.match(text)
    if m:
        year, month = (int(m.group(1)), int(m.group(2)))
        return f"{year:04d}-{month:02d}"

    m = _NUMERIC_YMD_RE.match(text)
    if m:
        year, month, day = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return f"{year:04d}-{month:02d}-{day:02d}"

    m = _NUMERIC_YM_RE.match(text)
    if m:
        year, month = (int(m.group(1)), int(m.group(2)))
        return f"{year:04d}-{month:02d}"

    for fmt in _EN_DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Keep non-Chinese unknown formats as-is; drop Chinese unknown formats.
    if _CJK_RE.search(text):
        return None
    return text
