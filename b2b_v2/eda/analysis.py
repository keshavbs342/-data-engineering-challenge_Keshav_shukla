"""eda/analysis.py – Statistical analysis + text report."""

from pathlib import Path
import numpy as np
import pandas as pd

from config.settings import PROCESSED
from utils.logger import get_logger

logger = get_logger(__name__)


def run_analysis(df: pd.DataFrame) -> dict:
    lines = []

    def h(t):  lines.append(f"\n{'='*60}\n  {t}\n{'='*60}")
    def p(t=""): lines.append(str(t))

    h("DATASET OVERVIEW")
    p(f"Records          : {len(df):,}")
    p(f"Columns          : {df.shape[1]}")
    p(f"Categories       : {df['category_label'].nunique()}")
    p(f"Unique suppliers : {df['supplier'].nunique():,}")
    p(f"Cities           : {df['city'].nunique():,}")

    h("MISSING VALUES")
    mv = (df.isnull().sum() / len(df) * 100).round(2).sort_values(ascending=False)
    mv = mv[mv > 0]
    p(mv.to_string() if not mv.empty else "None")

    h("PRICE STATISTICS (INR)")
    p(df["price"].describe(percentiles=[.1,.25,.5,.75,.9]).round(2).to_string())

    h("PRICE BY CATEGORY")
    p(df.groupby("category_label")["price"].agg(["count","mean","median","min","max"]).round(2).to_string())

    if "price_usd" in df.columns:
        h("PRICE IN USD (API-ENRICHED)")
        p(df.groupby("category_label")["price_usd"].agg(["mean","median"]).round(4).to_string())

    if "related_keywords" in df.columns:
        h("SAMPLE RELATED KEYWORDS (FROM API)")
        sample = df[df["related_keywords"].notna() & (df["related_keywords"] != "")][["title","related_keywords"]].head(10)
        p(sample.to_string(index=False))

    h("REGIONAL DISTRIBUTION")
    p(df["region"].value_counts().to_string())

    h("TOP 15 CITIES")
    p(df["city"].replace("", np.nan).dropna().value_counts().head(15).to_string())

    h("TOP 30 TITLE KEYWORDS")
    stop = {"the","and","for","with","of","in","a","an","to","by","from","or","is","at","on","be","as"}
    words = df["title"].str.lower().str.replace(r"[^a-z0-9 ]"," ",regex=True).str.split().explode().dropna()
    kf = words[~words.isin(stop) & (words.str.len()>2)].value_counts().head(30)
    p(kf.to_string())

    h("DATA QUALITY")
    p(df["quality_score"].describe().round(1).to_string())
    if "price_anomaly" in df.columns:
        p(f"\nPrice anomalies flagged: {df['price_anomaly'].sum()}")

    report = "\n".join(lines)
    rpath  = PROCESSED / "eda_report.txt"
    rpath.write_text(report)
    logger.info("EDA report → %s", rpath)

    stop_set = stop
    return {
        "n_records":            len(df),
        "n_categories":         df["category_label"].nunique(),
        "n_suppliers":          df["supplier"].nunique(),
        "price_coverage_pct":   round(df["price"].notna().mean()*100, 1),
        "avg_quality_score":    round(df["quality_score"].mean(), 1),
        "api_enriched":         "price_usd" in df.columns,
        "report_path":          str(rpath),
    }
