"""
config/settings.py
Central configuration. Override via environment variables where noted.
"""
import os
from pathlib import Path

BASE_DIR   = Path(__file__).resolve().parent.parent
DATA_DIR   = BASE_DIR / "data"
RAW_DIR    = DATA_DIR / "raw"
PROCESSED  = DATA_DIR / "processed"
PARTS_DIR  = DATA_DIR / "partitioned"
CHARTS_DIR = PROCESSED / "charts"
LOGS_DIR   = BASE_DIR / "logs"
DB_PATH    = BASE_DIR / "b2b_warehouse.duckdb"

for _d in (RAW_DIR, PROCESSED, PARTS_DIR, CHARTS_DIR, LOGS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ── Scraper ────────────────────────────────────────────────────────────────────
ASYNC_CONCURRENCY   = int(os.getenv("ASYNC_CONCURRENCY", "8"))
REQUEST_TIMEOUT     = int(os.getenv("REQUEST_TIMEOUT",    "15"))
MAX_RETRIES         = int(os.getenv("MAX_RETRIES",        "3"))
DELAY_MIN           = float(os.getenv("DELAY_MIN",        "0.5"))
DELAY_MAX           = float(os.getenv("DELAY_MAX",        "2.0"))
RECORDS_PER_CATEGORY = int(os.getenv("RECORDS_PER_CAT",  "120"))

TARGET_CATEGORIES = [
    "industrial-machinery",
    "electronics-components",
    "textile-fabric",
    "agriculture-equipment",
    "construction-materials",
]

# ── API enrichment ─────────────────────────────────────────────────────────────
# Uses the free Open Exchange Rates / RestCountries / REST Countries public APIs
# No key required for the APIs we use (RestCountries, Open Numbers, Datamuse)
ENRICH_APIS = {
    "currency": "https://open.er-api.com/v6/latest/INR",
    "keywords": "https://api.datamuse.com/words",   # free, no key
    "geo":      "https://restcountries.com/v3.1/name/india",
}

# ── ETL / DB ───────────────────────────────────────────────────────────────────
SCHEMA_VERSION      = "v2"
MIN_PRICE_VALID     = 1.0
MAX_PRICE_VALID     = 50_000_000.0
PARTITION_BY        = "category"          # column used for Parquet partitioning

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_LEVEL  = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-28s | %(message)s"
