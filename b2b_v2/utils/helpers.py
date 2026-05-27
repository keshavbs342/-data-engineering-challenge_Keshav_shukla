"""utils/helpers.py – Shared utility functions."""
import re, hashlib, time, random
from typing import Optional


def parse_price(s: str) -> Optional[float]:
    if not s or not isinstance(s, str):
        return None
    cleaned = s.replace(",", "").replace(" ", "")
    m = re.search(r"[\d]+(?:\.\d+)?", cleaned)
    return float(m.group()) if m else None


def make_id(*parts) -> str:
    return hashlib.md5("|".join(str(p) for p in parts).encode()).hexdigest()[:14]


def clean_text(t: str) -> str:
    return re.sub(r"\s+", " ", t or "").strip()


def jitter(lo: float, hi: float) -> None:
    time.sleep(random.uniform(lo, hi))
