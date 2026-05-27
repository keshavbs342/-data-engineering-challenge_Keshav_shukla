"""
etl/loader.py
=============
Persists cleaned data to three sinks:
  1. CSV  (human-readable)
  2. Partitioned Parquet (analytics / Spark-ready)
  3. DuckDB warehouse (SQL queries)
"""

from pathlib import Path
import pandas as pd

from config.settings import PROCESSED, PARTS_DIR, PARTITION_BY
from db.warehouse import Warehouse
from utils.logger import get_logger

logger = get_logger(__name__)


def load(df: pd.DataFrame, run_id: str = "manual") -> dict:
    paths = {}

    # ── CSV ────────────────────────────────────────────────────────────────────
    csv_path = PROCESSED / "products_cleaned.csv"
    df.to_csv(csv_path, index=False)
    logger.info("CSV → %s", csv_path)
    paths["csv"] = csv_path

    # ── Partitioned Parquet ────────────────────────────────────────────────────
    # Writes one sub-folder per category: data/partitioned/category=industrial-machinery/...
    df_pq = df.copy()
    for col in df_pq.select_dtypes(include="category").columns:
        df_pq[col] = df_pq[col].astype(str)
    part_col = PARTITION_BY if PARTITION_BY in df_pq.columns else None
    if part_col:
        for val, grp in df_pq.groupby(part_col):
            pdir = PARTS_DIR / f"{part_col}={val}"
            pdir.mkdir(parents=True, exist_ok=True)
            pfile = pdir / f"{run_id}.parquet"
            grp.drop(columns=[part_col]).to_parquet(pfile, index=False)
        logger.info("Partitioned Parquet → %s (%d partitions)", PARTS_DIR, df_pq[part_col].nunique())
    else:
        pfile = PROCESSED / "products_cleaned.parquet"
        df_pq.to_parquet(pfile, index=False)
        logger.info("Parquet → %s", pfile)
    paths["parquet_dir"] = PARTS_DIR

    # ── DuckDB ─────────────────────────────────────────────────────────────────
    wh = Warehouse()
    wh.start_run(source="etl_loader", records_in=len(df))
    n = wh.upsert_products(df)
    wh.finish_run(run_id=run_id, records_out=n)
    wh.print_summary()
    wh.close()
    paths["duckdb"] = wh.path

    return paths
