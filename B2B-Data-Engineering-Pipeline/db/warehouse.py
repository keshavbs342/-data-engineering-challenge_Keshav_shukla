"""
db/warehouse.py
===============
DuckDB-backed analytical warehouse.

Why DuckDB?
-----------
* Columnar, vectorised execution — fast analytics on millions of rows
* Zero-dependency server (single file, embedded like SQLite)
* Native Parquet read/write
* Full SQL with window functions, ASOF joins, QUALIFY
* Schema versioning via migration table

Schema
------
products           – fact table (one row per listing)
suppliers          – dimension (deduplicated supplier info)
ingestion_runs     – audit log (idempotency tracking)
schema_migrations  – schema version history
"""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd

from config.settings import DB_PATH, SCHEMA_VERSION
from utils.logger import get_logger

logger = get_logger(__name__)

DDL = """
-- ── Schema migrations tracker ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     VARCHAR PRIMARY KEY,
    applied_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description VARCHAR
);

-- ── Ingestion audit log ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id        VARCHAR PRIMARY KEY,
    started_at    TIMESTAMP,
    finished_at   TIMESTAMP,
    source        VARCHAR,
    records_in    INTEGER,
    records_out   INTEGER,
    status        VARCHAR DEFAULT 'running'
);

-- ── Supplier dimension ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id         VARCHAR PRIMARY KEY,
    name                VARCHAR NOT NULL,
    city                VARCHAR,
    state               VARCHAR,
    region              VARCHAR,
    rating              DOUBLE,
    response_rate_pct   DOUBLE,
    years_in_business   INTEGER,
    supplier_maturity   VARCHAR,
    certification       VARCHAR,
    first_seen          DATE,
    last_seen           DATE
);

-- ── Products fact table ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS products (
    id                  VARCHAR PRIMARY KEY,
    title               VARCHAR NOT NULL,
    category            VARCHAR,
    category_label      VARCHAR,
    price               DOUBLE,
    price_usd           DOUBLE,
    price_eur           DOUBLE,
    price_raw           VARCHAR,
    price_bucket        VARCHAR,
    price_anomaly       BOOLEAN DEFAULT FALSE,
    currency            VARCHAR DEFAULT 'INR',
    unit                VARCHAR,
    moq                 INTEGER,
    supplier_id         VARCHAR REFERENCES suppliers(supplier_id),
    location            VARCHAR,
    city                VARCHAR,
    state               VARCHAR,
    region              VARCHAR,
    rating              DOUBLE,
    response_rate_pct   DOUBLE,
    response_tier       VARCHAR,
    related_keywords    VARCHAR,
    country_region      VARCHAR,
    country_subregion   VARCHAR,
    certification       VARCHAR,
    listed_date         DATE,
    url                 VARCHAR,
    source              VARCHAR,
    quality_score       DOUBLE,
    schema_version      VARCHAR,
    ingested_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── Useful analytical views ─────────────────────────────────────────────────
CREATE OR REPLACE VIEW v_category_summary AS
SELECT
    category_label,
    COUNT(*)                                  AS total_listings,
    COUNT(price)                              AS priced_listings,
    ROUND(AVG(price), 2)                      AS avg_price_inr,
    ROUND(MEDIAN(price), 2)                   AS median_price_inr,
    ROUND(MIN(price), 2)                      AS min_price_inr,
    ROUND(MAX(price), 2)                      AS max_price_inr,
    ROUND(AVG(quality_score), 1)              AS avg_quality_score
FROM products
GROUP BY category_label;

CREATE OR REPLACE VIEW v_region_summary AS
SELECT
    region,
    COUNT(DISTINCT supplier_id)               AS unique_suppliers,
    COUNT(*)                                  AS total_listings,
    ROUND(AVG(price), 2)                      AS avg_price_inr,
    ROUND(AVG(quality_score), 1)              AS avg_quality
FROM products
GROUP BY region
ORDER BY total_listings DESC;

CREATE OR REPLACE VIEW v_top_suppliers AS
SELECT
    s.name,
    s.city,
    s.state,
    s.rating,
    s.response_rate_pct,
    s.years_in_business,
    COUNT(p.id)                               AS listing_count,
    ROUND(AVG(p.price), 2)                    AS avg_price
FROM suppliers s
JOIN products p USING (supplier_id)
GROUP BY ALL
ORDER BY listing_count DESC;
"""


class Warehouse:
    """Thin wrapper around a DuckDB connection with upsert helpers."""

    def __init__(self, path: Path = DB_PATH):
        self.path = path
        self.con  = duckdb.connect(str(path))
        self._bootstrap()

    def _bootstrap(self):
        self.con.execute(DDL)
        already = self.con.execute(
            "SELECT version FROM schema_migrations WHERE version = ?", [SCHEMA_VERSION]
        ).fetchone()
        if not already:
            self.con.execute(
                "INSERT INTO schema_migrations VALUES (?, ?, ?)",
                [SCHEMA_VERSION, datetime.now(), "Initial schema"],
            )
        logger.info("DuckDB warehouse ready → %s (schema %s)", self.path, SCHEMA_VERSION)

    # ── Ingestion helpers ──────────────────────────────────────────────────────

    def start_run(self, source: str, records_in: int) -> str:
        run_id = hashlib.md5(f"{source}{datetime.now()}".encode()).hexdigest()[:10]
        self.con.execute(
            "INSERT INTO ingestion_runs VALUES (?,?,?,?,?,?,?)",
            [run_id, datetime.now(), None, source, records_in, 0, "running"],
        )
        return run_id

    def finish_run(self, run_id: str, records_out: int, status: str = "success"):
        self.con.execute(
            "UPDATE ingestion_runs SET finished_at=?, records_out=?, status=? WHERE run_id=?",
            [datetime.now(), records_out, status, run_id],
        )

    # ── Upsert data ────────────────────────────────────────────────────────────

    def upsert_products(self, df: pd.DataFrame) -> int:
        """
        Upsert products + suppliers.
        Returns number of rows written.
        """
        df = df.copy()

        # ── suppliers dimension ────────────────────────────────────────────────
        sup_cols = ["supplier", "city", "state", "region",
                    "rating", "response_rate_pct", "years_in_business",
                    "supplier_maturity", "certification"]
        sup_df = df[[c for c in sup_cols if c in df.columns]].drop_duplicates(subset=["supplier"])
        sup_df = sup_df.rename(columns={"supplier": "name"})
        sup_df["supplier_id"] = sup_df["name"].apply(
            lambda n: hashlib.md5(n.encode()).hexdigest()[:14]
        )
        sup_df["first_seen"] = datetime.now().date()
        sup_df["last_seen"]  = datetime.now().date()

        self.con.register("_sup_stage", sup_df)
        self.con.execute("""
            INSERT INTO suppliers
            SELECT supplier_id, name, city, state, region,
                   rating, response_rate_pct,
                   TRY_CAST(years_in_business AS INTEGER),
                   CAST(supplier_maturity AS VARCHAR),
                   certification, first_seen, last_seen
            FROM _sup_stage
            ON CONFLICT (supplier_id) DO UPDATE SET
                last_seen           = EXCLUDED.last_seen,
                rating              = COALESCE(EXCLUDED.rating, suppliers.rating),
                response_rate_pct   = COALESCE(EXCLUDED.response_rate_pct, suppliers.response_rate_pct)
        """)
        self.con.unregister("_sup_stage")

        # ── products fact ──────────────────────────────────────────────────────
        df["supplier_id"] = df["supplier"].apply(
            lambda n: hashlib.md5(str(n).encode()).hexdigest()[:14]
        )

        # Stringify categoricals for DuckDB
        for col in df.select_dtypes(include="category").columns:
            df[col] = df[col].astype(str).replace("nan", None)

        # Subset to product schema columns
        keep = [
            "id", "title", "category", "category_label",
            "price", "price_usd", "price_eur", "price_raw", "price_bucket",
            "price_anomaly", "currency", "unit", "moq", "supplier_id",
            "location", "city", "state", "region", "rating",
            "response_rate_pct", "response_tier", "related_keywords",
            "country_region", "country_subregion", "certification",
            "listed_date", "url", "source", "quality_score", "schema_version",
        ]
        prod_df = df[[c for c in keep if c in df.columns]].copy()
        prod_df["ingested_at"] = datetime.now()
        self.con.register("_prod_stage", prod_df)
        self.con.execute("""
            INSERT INTO products
            SELECT * FROM _prod_stage
            ON CONFLICT (id) DO UPDATE SET
                price         = COALESCE(EXCLUDED.price, products.price),
                price_usd     = COALESCE(EXCLUDED.price_usd, products.price_usd),
                quality_score = EXCLUDED.quality_score,
                ingested_at   = EXCLUDED.ingested_at
        """)
        self.con.unregister("_prod_stage")

        n = self.con.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        logger.info("Warehouse: %d products total in DB", n)
        return n

    # ── Query helpers ──────────────────────────────────────────────────────────

    def query(self, sql: str) -> pd.DataFrame:
        return self.con.execute(sql).df()

    def print_summary(self):
        print("\n── Category Summary ──────────────────────────────────")
        print(self.query("SELECT * FROM v_category_summary").to_string(index=False))
        print("\n── Region Summary ────────────────────────────────────")
        print(self.query("SELECT * FROM v_region_summary").to_string(index=False))
        print("\n── Top 10 Suppliers ──────────────────────────────────")
        print(self.query("SELECT * FROM v_top_suppliers LIMIT 10").to_string(index=False))

    def close(self):
        self.con.close()
