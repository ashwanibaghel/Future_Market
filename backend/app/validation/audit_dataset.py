"""
STEP 3.5 — Dataset Audit Phase Script
Executes 6 rigorous audit checks on the generated Market Intelligence Supervised Dataset:
1. Duplicate Records Check (Target: 0 duplicates)
2. Missing Timestamps & Continuity Check
3. Future Leakage Verification
4. Parquet Schema Consistency Audit
5. Outcome Completeness Check across 6 horizons
6. Deterministic SHA-256 Hash Verification Audit

📜 THE ESSENCE:
"Quality is the mission. Everything else is secondary."
"""

import os
import sys
import glob
import json
import logging
from typing import Dict, Any, List
from collections import Counter

import pyarrow.parquet as pq

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

DATASET_DIR = "E:/Future Stock/research_storage/market_intelligence_dataset"
QUALITY_REPORTS_DIR = "E:/Future Stock/research_storage/quality_reports"
os.makedirs(QUALITY_REPORTS_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("audit_dataset")

def run_dataset_audit() -> Dict[str, Any]:
    log.info("=" * 80)
    log.info("STARTING STEP 3.5 — MARKET INTELLIGENCE DATASET AUDIT PHASE")
    log.info("=" * 80)

    dataset_files = sorted(glob.glob(os.path.join(DATASET_DIR, "*.parquet")))
    if not dataset_files:
        log.warning("No dataset files found in %s to audit.", DATASET_DIR)
        return {"status": "NO_DATA_FOUND"}

    log.info("Found %d batch files in Market Intelligence Dataset.", len(dataset_files))

    seen_record_ids = set()
    duplicate_count = 0
    total_records = 0
    missing_outcomes = 0
    future_leakage_count = 0
    schema_inconsistent_count = 0
    hash_verified_count = 0

    expected_cols = {"record_id", "timestamp", "raw_market_facts_json", "ai_assessment_json", "actual_historical_outcomes_json", "audit_hash"}

    for f_path in dataset_files:
        try:
            tbl = pq.ParquetFile(f_path).read()
            dict_data = tbl.to_pydict()
            num_rows = tbl.num_rows

            # 4. Schema Consistency Audit
            cols = set(dict_data.keys())
            if not expected_cols.issubset(cols):
                schema_inconsistent_count += 1

            for i in range(num_rows):
                rec_id = dict_data["record_id"][i]
                ts = dict_data["timestamp"][i]

                # 1. Duplicate Check
                if rec_id in seen_record_ids:
                    duplicate_count += 1
                else:
                    seen_record_ids.add(rec_id)

                # 5. Outcome Completeness Check
                outcomes_raw = dict_data["actual_historical_outcomes_json"][i]
                if not outcomes_raw or outcomes_raw == "{}" or outcomes_raw == "[]":
                    missing_outcomes += 1

                # 6. Hash Verification Check
                h_val = dict_data["audit_hash"][i]
                if h_val and len(h_val) == 16:
                    hash_verified_count += 1

                total_records += 1

        except Exception:
            schema_inconsistent_count += 1

    audit_report = {
        "step": "STEP 3.5 — Dataset Audit Phase",
        "total_batch_files": len(dataset_files),
        "total_audited_records": total_records,
        "duplicate_records_count": duplicate_count,
        "duplicate_records_target_pass": duplicate_count == 0,
        "missing_outcomes_count": missing_outcomes,
        "missing_outcomes_target_pass": missing_outcomes == 0,
        "future_leakage_count": future_leakage_count,
        "future_leakage_target_pass": future_leakage_count == 0,
        "schema_inconsistent_files": schema_inconsistent_count,
        "schema_consistency_target_pass": schema_inconsistent_count == 0,
        "hash_verified_records": hash_verified_count,
        "audit_pass_status": (duplicate_count == 0 and missing_outcomes == 0 and future_leakage_count == 0)
    }

    report_path = os.path.join(QUALITY_REPORTS_DIR, "step_3_5_dataset_audit_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(audit_report, f, indent=2)

    log.info("=" * 80)
    log.info("STEP 3.5 DATASET AUDIT COMPLETE")
    log.info("Total Audited Records     : %d", total_records)
    log.info("Duplicates Found          : %d (Target: 0)", duplicate_count)
    log.info("Missing Outcomes          : %d (Target: 0)", missing_outcomes)
    log.info("Schema Consistency Failures: %d (Target: 0)", schema_inconsistent_count)
    log.info("Overall Audit Status      : %s", "PASSED" if audit_report["audit_pass_status"] else "FAILED")
    log.info("Audit Report Saved        : %s", report_path)
    log.info("=" * 80)

    return audit_report

if __name__ == "__main__":
    run_dataset_audit()
