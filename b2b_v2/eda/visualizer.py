"""eda/visualizer.py – Generates EDA charts."""

from pathlib import Path
from typing import Dict
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from config.settings import CHARTS_DIR
from utils.logger import get_logger

logger = get_logger(__name__)
sns.set_theme(style="whitegrid", palette="muted", font_scale=1.05)
PAL = ["#2E86AB","#A23B72","#F18F01","#C73E1D","#3B1F2B","#44BBA4","#E94F37","#393E41"]


def _save(fig, name):
    p = CHARTS_DIR / f"{name}.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return p


def generate_all_charts(df: pd.DataFrame) -> Dict[str, Path]:
    charts = {}

    # 1 Category distribution
    fig, ax = plt.subplots(figsize=(10, 5))
    cc = df["category_label"].value_counts()
    b = ax.bar(cc.index, cc.values, color=PAL[:len(cc)], edgecolor="white")
    ax.bar_label(b, padding=4)
    ax.set_title("Listings by Category", fontweight="bold")
    ax.set_ylabel("Count"); plt.xticks(rotation=20, ha="right")
    charts["01_category_dist"] = _save(fig, "01_category_dist")

    # 2 Price distribution per category
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    for idx, (cat, sub) in enumerate(df.groupby("category_label")):
        ax = axes.flatten()[idx]
        prices = sub["price"].dropna()
        if len(prices):
            ax.hist(np.log10(prices+1), bins=25, color=PAL[idx%len(PAL)], alpha=0.85, edgecolor="white")
        ax.set_title(cat, fontsize=9, fontweight="bold")
        ax.set_xlabel("log₁₀(₹)")
    for i in range(idx+1, 6): axes.flatten()[i].set_visible(False)
    fig.suptitle("Price Distribution by Category (log scale)", fontweight="bold")
    plt.tight_layout()
    charts["02_price_dist"] = _save(fig, "02_price_dist")

    # 3 Price buckets stacked
    if "price_bucket" in df.columns:
        fig, ax = plt.subplots(figsize=(12, 6))
        pd.crosstab(df["category_label"], df["price_bucket"]).plot(
            kind="bar", stacked=True, ax=ax, colormap="tab10", edgecolor="white", linewidth=0.5)
        ax.set_title("Price Buckets by Category", fontweight="bold")
        ax.legend(title="Range", bbox_to_anchor=(1.01,1))
        plt.xticks(rotation=20, ha="right")
        charts["03_price_buckets"] = _save(fig, "03_price_buckets")

    # 4 Top cities
    fig, ax = plt.subplots(figsize=(10, 6))
    tc = df["city"].replace("", np.nan).dropna().value_counts().head(15)
    ax.barh(tc.index[::-1], tc.values[::-1], color="#2E86AB")
    ax.set_title("Top 15 Supplier Cities", fontweight="bold")
    ax.set_xlabel("Listings")
    for i, v in enumerate(tc.values[::-1]): ax.text(v+0.3, i, str(v), va="center", fontsize=9)
    charts["04_top_cities"] = _save(fig, "04_top_cities")

    # 5 Region pie
    if "region" in df.columns:
        fig, ax = plt.subplots(figsize=(8, 8))
        rc = df["region"].value_counts()
        ax.pie(rc.values, labels=rc.index, autopct="%1.1f%%",
               colors=PAL[:len(rc)], wedgeprops={"linewidth":1.5,"edgecolor":"white"})
        ax.set_title("Listings by Region", fontweight="bold")
        charts["05_region_pie"] = _save(fig, "05_region_pie")

    # 6 Rating dist
    if "rating" in df.columns:
        fig, ax = plt.subplots(figsize=(9, 5))
        df["rating"].dropna().hist(bins=20, ax=ax, color="#44BBA4", edgecolor="white")
        ax.axvline(df["rating"].mean(), color="#C73E1D", lw=2, ls="--",
                   label=f"Mean {df['rating'].mean():.2f}")
        ax.set_title("Supplier Rating Distribution", fontweight="bold")
        ax.legend(); ax.set_xlabel("Rating")
        charts["06_ratings"] = _save(fig, "06_ratings")

    # 7 Response rate boxplot
    if "response_rate_pct" in df.columns:
        fig, ax = plt.subplots(figsize=(11, 6))
        cats_u = df["category_label"].dropna().unique()
        bp = ax.boxplot(
            [df.loc[df["category_label"]==c,"response_rate_pct"].dropna().values for c in cats_u],
            labels=cats_u, patch_artist=True,
            medianprops={"color":"black","linewidth":2})
        for patch, col in zip(bp["boxes"], PAL): patch.set_facecolor(col); patch.set_alpha(0.75)
        ax.set_title("Response Rate by Category", fontweight="bold")
        ax.set_ylabel("Response Rate (%)"); plt.xticks(rotation=18, ha="right")
        charts["07_response_box"] = _save(fig, "07_response_box")

    # 8 Missing values heatmap
    fig, ax = plt.subplots(figsize=(12, 5))
    key_cols = [c for c in ["price","rating","response_rate_pct","years_in_business","city","price_usd"] if c in df.columns]
    mv = df[key_cols].isnull().mean().sort_values(ascending=False)*100
    mv = mv[mv>0]
    if not mv.empty:
        b = ax.bar(mv.index, mv.values,
               color=["#C73E1D" if v>20 else "#F18F01" if v>10 else "#44BBA4" for v in mv.values])
        ax.bar_label(b, fmt="%.1f%%", padding=3)
    ax.set_title("Missing Values %", fontweight="bold"); ax.set_ylabel("Missing (%)")
    charts["08_missing"] = _save(fig, "08_missing")

    # 9 Quality score
    fig, ax = plt.subplots(figsize=(9, 5))
    df["quality_score"].hist(bins=20, ax=ax, color="#A23B72", edgecolor="white")
    ax.axvline(df["quality_score"].mean(), color="#F18F01", lw=2, ls="--",
               label=f"Mean {df['quality_score'].mean():.1f}")
    ax.set_title("Data Quality Score Distribution", fontweight="bold")
    ax.legend(); ax.set_xlabel("Quality Score (0–100)")
    charts["09_quality"] = _save(fig, "09_quality")

    # 10 Price vs Rating
    if "rating" in df.columns:
        fig, ax = plt.subplots(figsize=(10, 6))
        prd = df[df["price"].notna() & df["rating"].notna()].copy()
        prd["lp"] = np.log10(prd["price"]+1)
        for idx, (cat, sub) in enumerate(prd.groupby("category_label")):
            ax.scatter(sub["lp"], sub["rating"], alpha=0.45, color=PAL[idx%len(PAL)], label=cat, s=22)
        ax.set_title("Price vs Supplier Rating", fontweight="bold")
        ax.set_xlabel("log₁₀(₹)"); ax.set_ylabel("Rating")
        ax.legend(title="Category", bbox_to_anchor=(1.01,1), fontsize=8)
        charts["10_price_vs_rating"] = _save(fig, "10_price_vs_rating")

    # 11 Keywords
    fig, ax = plt.subplots(figsize=(12, 6))
    stop = {"the","and","for","with","of","in","a","an","to","by","from","or","is","at","on","be","as"}
    tw = (df["title"].str.lower().str.replace(r"[^a-z0-9 ]"," ",regex=True)
          .str.split().explode().dropna())
    tw = tw[~tw.isin(stop) & (tw.str.len()>2)].value_counts().head(20)
    ax.barh(tw.index[::-1], tw.values[::-1], color="#2E86AB")
    ax.set_title("Top 20 Title Keywords", fontweight="bold"); ax.set_xlabel("Frequency")
    charts["11_keywords"] = _save(fig, "11_keywords")

    # 12 Supplier maturity
    if "supplier_maturity" in df.columns:
        fig, ax = plt.subplots(figsize=(9, 5))
        sm = df["supplier_maturity"].astype(str).replace("nan","Unknown").value_counts()
        b = ax.bar(sm.index, sm.values, color=PAL[:len(sm)], edgecolor="white")
        ax.bar_label(b, padding=4)
        ax.set_title("Supplier Maturity Breakdown", fontweight="bold"); ax.set_ylabel("Count")
        charts["12_supplier_maturity"] = _save(fig, "12_supplier_maturity")

    # 13 USD price comparison (API-enriched)
    if "price_usd" in df.columns:
        fig, ax = plt.subplots(figsize=(10, 5))
        pu = df.groupby("category_label")["price_usd"].median().sort_values()
        b = ax.barh(pu.index, pu.values, color="#F18F01")
        ax.bar_label(b, fmt="$%.1f", padding=3)
        ax.set_title("Median Price USD by Category (API-enriched)", fontweight="bold")
        ax.set_xlabel("Median USD Price")
        charts["13_usd_prices"] = _save(fig, "13_usd_prices")

    logger.info("Generated %d charts → %s", len(charts), CHARTS_DIR)
    return charts
