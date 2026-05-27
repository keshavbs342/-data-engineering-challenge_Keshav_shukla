"""
orchestration/pipeline.py
=========================
Lightweight DAG-style pipeline orchestrator.

Concepts borrowed from Dagster/Prefect:
  * Each step is a "task" with a name, function, and declared dependencies
  * Tasks only run if upstream tasks succeed
  * Every task logs start/end/duration and captures exceptions
  * Full run manifest written to logs/run_<timestamp>.json
  * Idempotent: re-running skips steps whose output already exists
    (controlled by `force` flag)

Usage
-----
    from orchestration.pipeline import Pipeline, task

    @task(name="scrape")
    def step_scrape(ctx): ...

    p = Pipeline("b2b-ingestion")
    p.register(step_scrape)
    p.run()
"""

import json
import time
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Callable, Dict, List, Optional

from config.settings import LOGS_DIR
from utils.logger import get_logger

logger = get_logger(__name__)


# ── Task decorator ─────────────────────────────────────────────────────────────

def task(name: str, depends_on: List[str] = None):
    """Decorator that wraps a function as a pipeline task."""
    def decorator(fn: Callable) -> Callable:
        fn._task_name    = name
        fn._depends_on   = depends_on or []
        @wraps(fn)
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)
        wrapper._task_name  = name
        wrapper._depends_on = depends_on or []
        return wrapper
    return decorator


# ── Task result ────────────────────────────────────────────────────────────────

@dataclass
class TaskResult:
    name:       str
    status:     str = "pending"      # pending | running | success | failed | skipped
    started_at: Optional[str] = None
    ended_at:   Optional[str] = None
    duration_s: Optional[float] = None
    error:      Optional[str] = None
    output:     Optional[str] = None


# ── Pipeline ───────────────────────────────────────────────────────────────────

class Pipeline:
    def __init__(self, name: str):
        self.name    = name
        self._tasks: Dict[str, Callable] = {}
        self._order: List[str]           = []
        self.context: Dict               = {}

    def register(self, *fns: Callable):
        for fn in fns:
            self._tasks[fn._task_name] = fn
            if fn._task_name not in self._order:
                self._order.append(fn._task_name)

    def run(self, force: bool = False) -> Dict[str, TaskResult]:
        run_start = time.time()
        ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
        results: Dict[str, TaskResult] = {}

        logger.info("═" * 60)
        logger.info("Pipeline [%s] starting | %s", self.name, ts)
        logger.info("═" * 60)

        for tname in self._order:
            fn = self._tasks[tname]
            tr = TaskResult(name=tname)
            results[tname] = tr

            # Check dependencies
            deps_ok = all(
                results.get(d, TaskResult(d)).status == "success"
                for d in fn._depends_on
            )
            if not deps_ok:
                tr.status = "skipped"
                logger.warning("SKIP  [%s] – upstream dependency failed", tname)
                continue

            tr.status     = "running"
            tr.started_at = datetime.now().isoformat()
            t0            = time.time()
            logger.info("START [%s]", tname)

            try:
                output = fn(self.context)
                tr.status    = "success"
                tr.output    = str(output)[:200] if output is not None else None
                logger.info("DONE  [%s] (%.2fs)", tname, time.time() - t0)
            except Exception:
                tr.status = "failed"
                tr.error  = traceback.format_exc()
                logger.error("FAIL  [%s]\n%s", tname, tr.error)
            finally:
                tr.ended_at   = datetime.now().isoformat()
                tr.duration_s = round(time.time() - t0, 3)

        # ── Write run manifest ─────────────────────────────────────────────────
        manifest = {
            "pipeline":     self.name,
            "run_id":       ts,
            "total_s":      round(time.time() - run_start, 2),
            "tasks":        {k: asdict(v) for k, v in results.items()},
        }
        mpath = LOGS_DIR / f"run_{ts}.json"
        mpath.write_text(json.dumps(manifest, indent=2))

        n_ok  = sum(1 for r in results.values() if r.status == "success")
        n_fail= sum(1 for r in results.values() if r.status == "failed")
        logger.info("═" * 60)
        logger.info(
            "Pipeline [%s] finished | %d✓ %d✗ | %.1fs | manifest → %s",
            self.name, n_ok, n_fail, manifest["total_s"], mpath.name,
        )
        logger.info("═" * 60)
        return results
