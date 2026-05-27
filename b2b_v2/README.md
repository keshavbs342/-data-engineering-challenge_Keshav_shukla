# B2B Marketplace Data Engineering Pipeline v2

Production-grade, fault-tolerant ingestion and analytics pipeline for B2B marketplace data (IndiaMART / Alibaba-style). Built with a startup/ownership mindset — not a demo, a deployable system.

---

## Architecture

```
                ┌─────────────────────────────────────────────┐
                │           DAG Orchestrator                  │
                │  scrape → enrich → transform → load → eda  │
                └─────────────────────────────────────────────┘
                       │              │              │
               ┌───────┘      ┌───────┘      ┌──────┘
               ▼              ▼              ▼
        Async Scraper    Real APIs      DuckDB Warehouse
        (aiohttp +       (exchange      + Partitioned
         semaphore +      rates,         Parquet
         checkpoint +     geo,           + CSV
         back-off)        keywords)
```

---

## What's production-grade here

| Feature | Implementation |
|---|---|
| **Async concurrency** | `aiohttp` + `asyncio.Semaphore(8)` — 8 concurrent workers |
| **Retry + back-off** | `tenacity` exponential back-off; 30s hold on 429 |
| **Idempotency** | URL checkpoint file — re-runs skip already-scraped pages |
| **Real API integration** | Open Exchange Rates + Datamuse + RestCountries (all free, no key) |
| **Database layer** | DuckDB with fact/dimension schema, upsert, audit log, SQL views |
| **Partitioned storage** | Parquet partitioned by `category=` for efficient predicate pushdown |
| **Schema versioning** | `schema_migrations` table tracks applied versions |
| **DAG orchestration** | Custom `@task(depends_on=[...])` decorator with run manifests |
| **Observability** | Rotating file logs + per-run JSON manifest in `logs/` |
| **Fault tolerance** | Failed tasks skip dependents; pipeline still writes manifests |

---

## Quick start

```bash
# 1. Install (Python 3.9+)
pip install -r requirements.txt

# 2. Full pipeline (mock data + real API enrichment)
python main.py

# 3. Options
python main.py --mode scrape     # data collection only
python main.py --mode etl        # transform + load only
python main.py --mode eda        # charts + report only
python main.py --live            # live IndiaMART scraper (needs network)
python main.py --no-enrich       # skip API enrichment
python main.py --records 200     # 200 records per category (default 120)
```

---

## Output artifacts

| Artifact | Location | Description |
|---|---|---|
| Raw JSON | `data/raw/products_*.json` | Timestamped scrape output |
| Cleaned CSV | `data/processed/products_cleaned.csv` | Full cleaned dataset |
| Partitioned Parquet | `data/partitioned/category=*/` | Analytics-ready, partition-prunable |
| DuckDB warehouse | `b2b_warehouse.duckdb` | SQL-queryable, with views |
| EDA report | `data/processed/eda_report.txt` | Full statistical analysis |
| Charts (13) | `data/processed/charts/*.png` | All visualisations |
| Run manifest | `logs/run_<ts>.json` | DAG execution trace |
| Pipeline log | `logs/pipeline.log` | Rotating file log |

---

## Query the warehouse

```python
import duckdb
con = duckdb.connect("b2b_warehouse.duckdb")

# Pre-built analytical views
con.sql("SELECT * FROM v_category_summary").show()
con.sql("SELECT * FROM v_region_summary").show()
con.sql("SELECT * FROM v_top_suppliers LIMIT 10").show()

# Ad-hoc SQL
con.sql("""
    SELECT category_label, region, COUNT(*) as listings,
           ROUND(AVG(price_usd), 2) as avg_usd
    FROM products
    WHERE price IS NOT NULL
    GROUP BY ALL
    ORDER BY listings DESC
""").show()
```

---

## API enrichment layer

Three real public APIs are called per run (no API key required):

1. **open.er-api.com** — live INR→USD/EUR exchange rates → adds `price_usd`, `price_eur` columns
2. **api.datamuse.com** — semantic keyword expansion per product title → adds `related_keywords`
3. **restcountries.com** — India country metadata → adds `country_region`, `country_subregion`

All calls are async, fault-tolerant, and cached within a session. On network failure, sensible fallbacks are used so the pipeline doesn't crash.

---

## Extending the pipeline

**Swap in a real scraper:**
```python
# scraper/indiamart_async.py already has the structure
# Just add a --live flag call
python main.py --live
```

**Add a new pipeline task:**
```python
@task(name="validate", depends_on=["transform"])
def step_validate(ctx):
    df = ctx["df"]
    assert df["id"].is_unique, "Duplicate IDs found"
    # ... custom validation
```

**Add more API sources:**
```python
# api/enricher.py — add to enrich_batch()
hsn_data = await fetch_hsn_codes(session, rec["category"])
rec["hsn_code"] = hsn_data.get("code")
```

---

## Project structure

```
b2b_v2/
├── main.py                         ← DAG entry point
├── requirements.txt
├── config/settings.py              ← all config, env-overridable
├── scraper/
│   ├── async_scraper.py            ← async base (semaphore, retry, checkpoint)
│   ├── indiamart_async.py          ← real scraper (BS4 parser)
│   └── mock_scraper.py             ← realistic synthetic data
├── api/
│   └── enricher.py                 ← async API calls (3 real public APIs)
├── etl/
│   ├── transformer.py              ← clean, normalise, derive, score
│   └── loader.py                   ← CSV + partitioned Parquet + DuckDB
├── db/
│   └── warehouse.py                ← DuckDB schema, upsert, SQL views
├── orchestration/
│   └── pipeline.py                 ← @task DAG with manifests
├── eda/
│   ├── analysis.py                 ← stats + text report
│   └── visualizer.py               ← 13 charts
└── utils/
    ├── logger.py                   ← dual-sink (console + file)
    └── helpers.py
```
