# B2B Data Engineering Pipeline

A production-style data engineering pipeline built using Python, AsyncIO, DuckDB, and Parquet to simulate real-world B2B marketplace data ingestion and analytics workflows.

This project demonstrates:

* Async web scraping & API integrations
* ETL pipeline architecture
* Data cleaning & transformation
* Analytical warehousing using DuckDB
* Partitioned Parquet storage
* Orchestration & fault tolerance
* Exploratory data analysis (EDA)

---

# Architecture Overview

```text
                ┌──────────────────┐
                │  Data Sources    │
                │------------------│
                │ IndiaMART Pages  │
                │ REST APIs        │
                └────────┬─────────┘
                         │
                         ▼
              ┌────────────────────┐
              │ Async Scraper Layer │
              │ aiohttp + asyncio   │
              └────────┬───────────┘
                       │
                       ▼
              ┌────────────────────┐
              │ Raw Data Storage   │
              │ JSON / checkpoints │
              └────────┬───────────┘
                       │
                       ▼
              ┌────────────────────┐
              │ ETL Transformer    │
              │ Cleaning + Dedupe  │
              └────────┬───────────┘
                       │
                       ▼
              ┌────────────────────┐
              │ Partitioned Parquet│
              │ category/date wise │
              └────────┬───────────┘
                       │
                       ▼
              ┌────────────────────┐
              │ DuckDB Warehouse   │
              │ Analytics Layer    │
              └────────┬───────────┘
                       │
                       ▼
              ┌────────────────────┐
              │ EDA & Insights     │
              └────────────────────┘
```

---

# Features

## Async Web Scraping

* Built with `asyncio` and `aiohttp`
* Concurrent request handling using semaphores
* Retry logic with exponential backoff
* Fault-tolerant scraping pipeline

## ETL Workflows

* Raw → Clean → Enriched → Analytics flow
* Data validation and normalization
* Deduplication support
* Schema-safe transformations

## Storage & Analytics

* DuckDB analytical warehouse
* Partitioned Parquet datasets
* Optimized analytical querying
* Aggregations and anomaly detection

## Orchestration

* Custom lightweight task orchestration
* Dependency-aware execution flow
* Pipeline manifests & logging
* Idempotent re-runs

## Exploratory Data Analysis

* Trend analysis
* Price anomaly detection
* Category-level aggregations
* Structured reporting

---

# Tech Stack

| Category         | Tools               |
| ---------------- | ------------------- |
| Language         | Python              |
| Async Networking | asyncio, aiohttp    |
| Parsing          | BeautifulSoup       |
| Data Processing  | pandas, numpy       |
| Storage          | Parquet             |
| Warehouse        | DuckDB              |
| Retry Handling   | tenacity            |
| Visualization    | matplotlib          |
| Orchestration    | Custom DAG pipeline |

---

# Project Structure

```text
project/
│
├── scraper/
│   ├── async_scraper.py
│   ├── indiamart_async.py
│
├── etl/
│   ├── transformer.py
│   ├── loader.py
│
├── orchestration/
│   ├── pipeline.py
│
├── warehouse/
│   ├── warehouse.py
│
├── analytics/
│   ├── eda.py
│
├── utils/
│   ├── helpers.py
│
├── tests/
│   ├── test_transformer.py
│
├── data/
│   ├── raw/
│   ├── parquet/
│   ├── warehouse/
│
├── logs/
│
├── requirements.txt
├── main.py
└── README.md
```

---

# Installation

Clone the repository:

```bash
git clone <your-repo-link>
cd <repo-name>
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# Running the Pipeline

Run the default mock pipeline:

```bash
python main.py --mode full
```

Run live scraping mode:

```bash
python main.py --live
```

Run analytics only:

```bash
python main.py --eda
```

---

# Example Pipeline Flow

1. URLs enter async scraping queue
2. Semaphore controls concurrent requests
3. HTML pages are fetched asynchronously
4. Raw product data is extracted
5. ETL layer cleans & validates records
6. Duplicates are removed
7. Data is stored as partitioned Parquet
8. DuckDB warehouse loads analytical tables
9. EDA generates insights & summaries

---

# Idempotency & Reliability

The pipeline is designed to safely support re-runs.

Implemented using:

* checkpoint tracking
* deduplication logic
* retry handling
* upsert-style warehouse loading

This prevents duplicate ingestion and supports fault recovery.

---

# Testing

Run tests using:

```bash
pytest tests/
```

Example test coverage includes:

* price parsing
* deduplication validation
* anomaly detection
* missing field handling

---

# Note on Live Scraping

IndiaMART renders portions of its product content dynamically and may periodically update its HTML structure.

The `--live` scraper targets lightweight directory endpoints that are generally more stable, but selectors may require updates over time.

The default mock pipeline mode is the validated and reliable execution path for this submission.

In a production setting, this scraper would be paired with:

* Playwright/Selenium
* selector monitoring
* rotating proxies
* observability dashboards

---

# Future Improvements

* Dagster/Prefect orchestration
* GraphQL integrations
* Kafka-based streaming ingestion
* Vector database support
* Docker deployment
* Airflow scheduling
* CI/CD pipelines
* Distributed scraping

---

# Why DuckDB + Parquet?

DuckDB was chosen because it:

* is columnar and analytics-optimized
* works directly with Parquet
* requires no server setup
* performs extremely well for local analytical workloads

Partitioned Parquet storage enables efficient querying by reducing unnecessary data scans.

---

# Key Engineering Concepts Demonstrated

* Async concurrency
* ETL architecture
* Idempotent pipelines
* Fault tolerance
* Retry mechanisms
* Data warehousing
* Analytical query optimization
* Partitioned storage
* Orchestration fundamentals

---

# Author

Keshav Shukla

* Python Developer
* Data Engineering Enthusiast
* AI & Analytics Focused

Email: keshavbs342@gmail.com
