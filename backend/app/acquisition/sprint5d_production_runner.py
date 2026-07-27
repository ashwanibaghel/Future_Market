import os
import json
import time
import logging
from datetime import datetime, timezone

from app.acquisition.engine import HistoricalBackfillEngine, PROGRESS_FILE
from app.acquisition.replay_indexer import ReplayIndexBuilder
from app.research_os.governance.dataset_registry import (
    DatasetRegistry,
    PARQUET_LAKE_DIR,
    RESEARCH_STORAGE_DIR,
    QUALITY_REPORTS_DIR,
    ensure_research_storage_structure,
)
from app.acquisition.sprint5c_data_lake_builder import run_sprint5c_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("acquisition.sprint5d_runner")


def run_sprint5d_production_acquisition():
    """
    Sprint 5D: Production Historical Data Acquisition Engine.
    Executes full 5-year download (2021 - Present) for NIFTY and BANKNIFTY.
    """
    logger.info("=========================================================")
    logger.info("STARTING SPRINT 5D — PRODUCTION HISTORICAL DATA ACQUISITION")
    logger.info("Target Symbols: NIFTY, BANKNIFTY | Range: 2021 -> 2026")
    logger.info("=========================================================")

    ensure_research_storage_structure()
    engine = HistoricalBackfillEngine()

    t_start = time.time()

    # Execute 5-year backfill for NIFTY and BANKNIFTY
    res = engine.execute_5year_backfill(
        symbols=["NIFTY", "BANKNIFTY"],
        start_year=2021,
        end_year=2026,
    )

    t_elapsed = time.time() - t_start
    logger.info("Backfill execution cycle completed in %.2f seconds.", t_elapsed)

    # Re-build Replay Index and Data Lake Final Report
    sprint5c_summary = run_sprint5c_pipeline()

    final_report = {
        "sprint": "5D",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total_execution_time_seconds": round(t_elapsed, 2),
        "backfill_result": res,
        "lake_summary": sprint5c_summary,
    }

    report_file = os.path.join(QUALITY_REPORTS_DIR, "sprint5d_completion_report.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(final_report, f, indent=2)

    logger.info("Sprint 5D completion report saved to %s", report_file)
    return final_report


if __name__ == "__main__":
    run_sprint5d_production_acquisition()
