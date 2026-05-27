"""
etl/transformer.py
==================
Cleans, normalises, deduplicates, and enriches raw product records.
Includes schema versioning and data-quality scoring.
"""

from typing import List, Dict
import pandas as pd
import numpy as np

from config.settings import MIN_PRICE_VALID, MAX_PRICE_VALID, SCHEMA_VERSION
from utils.helpers import parse_price
from utils.logger import get_logger

logger = get_logger(__name__)

CATEGORY_LABELS = {
    "industrial-machinery":   "Industrial Machinery",
    "electronics-components": "Electronics Components",
    "textile-fabric":         "Textile & Fabric",
    "agriculture-equipment":  "Agriculture Equipment",
    "construction-materials": "Construction Materials",
}

REGION_MAP = {
    "Maharashtra": "West",  "Gujarat": "West",     "Rajasthan": "West",   "Goa": "West",
    "Delhi":       "North", "Haryana": "North",    "Punjab": "North",
    "Uttar Pradesh": "North", "Uttarakhand": "North",
    "Tamil Nadu":  "South", "Telangana": "South",  "Andhra Pradesh": "South",
    "Kerala":      "South", "Karnataka": "South",
    "West Bengal": "East",  "Odisha": "East",      "Bihar": "East",
    "Jharkhand":   "East",  "Assam": "East",
    "Madhya Pradesh": "Central", "Chhattisgarh": "Central",
}


def transform(records: List[Dict]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    n0 = len(df)
    logger.info("Transform start: %d records", n0)

    # ── Schema version tag ─────────────────────────────────────────────────────
    df["schema_version"] = SCHEMA_VERSION

    # ── Deduplicate ────────────────────────────────────────────────────────────
    df = df.drop_duplicates(subset=["id"])
    logger.info("Dedup: removed %d duplicates", n0 - len(df))

    # ── Price ──────────────────────────────────────────────────────────────────
    if "price" not in df.columns:
        df["price"] = np.nan
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    mask = df["price"].isna()
    df.loc[mask, "price"] = pd.to_numeric(
        df.loc[mask, "price_raw"].apply(parse_price), errors="coerce"
    )
    # Flag and null anomalies
    bad = (df["price"] < MIN_PRICE_VALID) | (df["price"] > MAX_PRICE_VALID)
    df["price_anomaly"] = bad.fillna(False)
    df.loc[bad, "price"] = np.nan
    df["currency"] = df.get("currency", pd.Series(["INR"] * len(df))).fillna("INR")

    # ── Category / region ──────────────────────────────────────────────────────
    df["category_label"] = df["category"].map(CATEGORY_LABELS).fillna(df["category"])
    for col in ("city", "state", "location"):
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").str.strip()
    df["region"] = df["state"].map(REGION_MAP).fillna("Other")

    # ── Derived / bucketed columns ─────────────────────────────────────────────
    df["price_bucket"] = pd.cut(
        df["price"],
        bins=[0, 1_000, 10_000, 1_00_000, 10_00_000, float("inf")],
        labels=["<1K", "1K–10K", "10K–1L", "1L–10L", ">10L"],
        right=False,
    )

    if "response_rate_pct" in df.columns:
        df["response_rate_pct"] = pd.to_numeric(df["response_rate_pct"], errors="coerce")
        df["response_tier"] = pd.cut(
            df["response_rate_pct"],
            bins=[0, 60, 80, 95, 101],
            labels=["Low", "Medium", "High", "Excellent"],
            right=False,
        )

    if "rating" in df.columns:
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce").clip(1.0, 5.0)

    if "years_in_business" in df.columns:
        df["years_in_business"] = pd.to_numeric(df["years_in_business"], errors="coerce")
        df["supplier_maturity"] = pd.cut(
            df["years_in_business"],
            bins=[0, 3, 7, 15, float("inf")],
            labels=["Startup", "Growing", "Established", "Veteran"],
        )

    # ── Quality score ──────────────────────────────────────────────────────────
    quality_cols = [c for c in ["price", "supplier", "city", "rating", "response_rate_pct"] if c in df.columns]
    df["quality_score"] = (df[quality_cols].notna().sum(axis=1) / len(quality_cols) * 100).round(1)

    logger.info(
        "Transform done: %d records | %.1f%% priced | avg quality %.1f",
        len(df), df["price"].notna().mean() * 100, df["quality_score"].mean(),
    )
    return df
