"""
main.py
=======
Entry point for the B2B Data Engineering Pipeline.

Registers each stage as a DAG task, then runs via the Pipeline orchestrator.
Every run produces a JSON manifest in logs/ for observability.

Usage
-----
    python main.py                   # full pipeline (mock data + API enrichment)
    python main.py --mode scrape     # only collect data
    python main.py --mode etl        # transform + load only
    python main.py --mode eda        # charts + report only
    python main.py --live            # use live IndiaMART scraper (needs network)
    python main.py --no-enrich       # skip API enrichment
    python main.py --records 200     # 200 mock records per category
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import TARGET_CATEGORIES, RECORDS_PER_CATEGORY, RAW_DIR
from orchestration.pipeline import Pipeline, task
from utils.logger import get_logger

logger = get_logger("main")


def parse_args():
    p = argparse.ArgumentParser(description="B2B Data Engineering Pipeline v2")
    p.add_argument("--mode",      choices=["full","scrape","etl","eda"], default="full")
    p.add_argument("--live",      action="store_true", help="Use live IndiaMART scraper")
    p.add_argument("--no-enrich", action="store_true", help="Skip API enrichment")
    p.add_argument("--records",   type=int, default=RECORDS_PER_CATEGORY)
    return p.parse_args()


def build_pipeline(args) -> Pipeline:
    pipe = Pipeline("b2b-ingestion-v2")

    # ── Task 1: Scrape ─────────────────────────────────────────────────────────
    @task(name="scrape")
    def step_scrape(ctx):
        if args.live:
            from scraper.indiamart_async import IndiaMARTAsyncScraper
            scraper = IndiaMARTAsyncScraper()
            records = asyncio.run(scraper.scrape_all(TARGET_CATEGORIES))
            logger.info("Live scraper returned %d records", len(records))
        else:
            from scraper.mock_scraper import generate
            records = generate(TARGET_CATEGORIES, per_category=args.records)
            logger.info("Mock scraper generated %d records", len(records))

        ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = RAW_DIR / f"products_{ts}.json"
        out.write_text(json.dumps(records, ensure_ascii=False, indent=2))
        logger.info("Raw data → %s (%d records)", out, len(records))
        ctx["raw_path"] = str(out)
        ctx["records"]  = records
        return str(out)

    # ── Task 2: API Enrich ─────────────────────────────────────────────────────
    @task(name="enrich", depends_on=["scrape"])
    def step_enrich(ctx):
        if args.no_enrich:
            logger.info("API enrichment skipped (--no-enrich)")
            return "skipped"
        from api.enricher import enrich_batch
        records = ctx.get("records", [])
        enriched = asyncio.run(enrich_batch(records))
        ctx["records"] = enriched
        logger.info("API enrichment complete: %d records", len(enriched))
        return f"{len(enriched)} records enriched"

    # ── Task 3: Transform ──────────────────────────────────────────────────────
    @task(name="transform", depends_on=["enrich"])
    def step_transform(ctx):
        from etl.transformer import transform
        records = ctx.get("records")
        if not records:
            import json
            records = json.loads(Path(ctx["raw_path"]).read_text())
        df = transform(records)
        ctx["df"] = df
        logger.info("Transform: %d rows × %d cols", df.shape[0], df.shape[1])
        return f"{df.shape}"

    # ── Task 4: Load ───────────────────────────────────────────────────────────
    @task(name="load", depends_on=["transform"])
    def step_load(ctx):
        from etl.loader import load
        df    = ctx["df"]
        ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
        paths = load(df, run_id=ts)
        ctx["load_paths"] = paths
        return str({k: str(v) for k, v in paths.items()})

    # ── Task 5: EDA ────────────────────────────────────────────────────────────
    @task(name="eda", depends_on=["load"])
    def step_eda(ctx):
        import pandas as pd
        from config.settings import PROCESSED
        from eda.analysis import run_analysis
        from eda.visualizer import generate_all_charts

        df = ctx.get("df"); df = pd.read_csv(PROCESSED / "products_cleaned.csv") if df is None else df
        stats  = run_analysis(df)
        charts = generate_all_charts(df)

        logger.info("\n╔══════════════════════════════════════╗")
        logger.info("║         EDA SUMMARY                  ║")
        logger.info("╠══════════════════════════════════════╣")
        logger.info("║  Records        : %-18d║", stats["n_records"])
        logger.info("║  Categories     : %-18d║", stats["n_categories"])
        logger.info("║  Suppliers      : %-18d║", stats["n_suppliers"])
        logger.info("║  Price coverage : %-17s ║", f"{stats['price_coverage_pct']}%")
        logger.info("║  Avg quality    : %-17s ║", f"{stats['avg_quality_score']}/100")
        logger.info("║  API-enriched   : %-18s║", str(stats["api_enriched"]))
        logger.info("║  Charts         : %-18d║", len(charts))
        logger.info("╚══════════════════════════════════════╝")
        return f"{len(charts)} charts"

    # Register only what's needed for this mode
    mode_tasks = {
        "scrape": [step_scrape],
        "etl":    [step_scrape, step_enrich, step_transform, step_load],
        "eda":    [step_scrape, step_enrich, step_transform, step_load, step_eda],
        "full":   [step_scrape, step_enrich, step_transform, step_load, step_eda],
    }
    pipe.register(*mode_tasks[args.mode])
    return pipe


if __name__ == "__main__":
    args = build_pipeline_args = parse_args()
    pipe = build_pipeline(args)
    results = pipe.run()
    failed = [n for n, r in results.items() if r.status == "failed"]
    sys.exit(1 if failed else 0)
