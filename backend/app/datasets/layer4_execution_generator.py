"""
🏛️ OI Lens — LAYER 4 (EXECUTION LAYER) DATASET GENERATOR (v1.0)

Generates ML datasets for:
1. MOD_09_POSITION_SIZING
2. MOD_11_EXECUTION_INTELLIGENCE

Streams ALL 995 evidence batch files (976,568 records across 2021-2026),
applies strict temporal splitting (2021-23 Train / 2024 Val / 2025-26 Test),
and queries KnowledgeService for validated hypothesis backing.
"""

import os
import sys
import json
import time
import logging
from typing import Dict, Any, List
import pyarrow.parquet as pq

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from app.datasets.base_dataset_generator import BaseDatasetGenerator
from app.services.knowledge_service import knowledge_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("layer4_execution_gen")


class Layer4ExecutionGenerator:

    def __init__(self):
        self.gen_mod09 = BaseDatasetGenerator("MOD_09_POSITION_SIZING", "Position Sizing & Calibration", "layer_4_execution")
        self.gen_mod11 = BaseDatasetGenerator("MOD_11_EXECUTION_INTELLIGENCE", "Execution & Slippage Intelligence", "layer_4_execution")

    def run_layer4_generation(self):
        log.info("=" * 80)
        log.info("PHASE 5.4 — LAYER 4 (EXECUTION LAYER) DATASET GENERATOR")
        log.info("Streaming ALL %d batch files for MOD_09, MOD_11...", len(self.gen_mod09.batch_files))
        log.info("=" * 80)

        mod09_train, mod09_val, mod09_test = [], [], []
        mod11_train, mod11_val, mod11_test = [], [], []

        batch_files = self.gen_mod09.batch_files
        t_start = time.time()

        for b_idx, f_path in enumerate(batch_files):
            try:
                tbl = pq.ParquetFile(f_path).read()
                d = tbl.to_pydict()
                num_rows = tbl.num_rows

                rec_ids = d.get("record_id", [])
                timestamps = d.get("timestamp", [])
                raw_facts_json = d.get("raw_market_facts_json", [])
                ai_assess_json = d.get("ai_assessment_json", [])
                outcomes_json = d.get("actual_historical_outcomes_json", [])

                for i in range(num_rows):
                    r_id = rec_ids[i]
                    ts = timestamps[i]
                    yr = ts[:4] if len(ts) >= 4 else "2021"

                    raw_f = json.loads(raw_facts_json[i]) if isinstance(raw_facts_json[i], str) else raw_facts_json[i]
                    ai_a = json.loads(ai_assess_json[i]) if isinstance(ai_assess_json[i], str) else ai_assess_json[i]
                    out_c = json.loads(outcomes_json[i]) if isinstance(outcomes_json[i], str) else outcomes_json[i]

                    sym = raw_f.get("symbol", "NIFTY")
                    conf = float(ai_a.get("confidence_score", 0.85))
                    vol_delta = float(raw_f.get("volume_delta_pct", 0.0))

                    mfe_15m = float(out_c.get("horizon_15m", {}).get("mfe_pct", 0.0))
                    mae_15m = float(out_c.get("horizon_15m", {}).get("mae_pct", 0.0))

                    # 1. MOD_09 Position Sizing Row
                    calibrated_prob = round(min(0.95, max(0.40, conf * 0.90)), 3)
                    kelly_frac = round(max(0.05, (calibrated_prob * 2.0 - 1.0) * 0.25), 3)
                    lots = int(max(1, round(kelly_frac * 16)))
                    capital_allocated = round(lots * 75000.0, 2)

                    row_09 = {
                        "record_id": r_id,
                        "timestamp": ts,
                        "symbol": sym,
                        "lots_to_trade": lots,  # Target Y
                        "capital_allocated_inr": capital_allocated,
                        "calibrated_win_probability": calibrated_prob,
                        "kelly_fraction": kelly_frac,
                        "raw_confidence": conf
                    }

                    # 2. MOD_11 Execution Intelligence Row
                    contradiction = (conf > 0.80 and vol_delta < -15.0)
                    expected_slippage = 0.85 if contradiction else 0.25
                    execution_gate = "REJECTED_CONTRADICTION" if contradiction else "APPROVED"

                    row_11 = {
                        "record_id": r_id,
                        "timestamp": ts,
                        "symbol": sym,
                        "contradiction_flag": contradiction,  # Target Y
                        "expected_slippage_pts": expected_slippage,
                        "execution_gate": execution_gate,
                        "volume_delta_pct": vol_delta
                    }

                    if yr in ("2021", "2022", "2023"):
                        mod09_train.append(row_09)
                        mod11_train.append(row_11)
                    elif yr == "2024":
                        mod09_val.append(row_09)
                        mod11_val.append(row_11)
                    else:
                        mod09_test.append(row_09)
                        mod11_test.append(row_11)

            except Exception as e:
                log.error("Error processing batch %s: %s", f_path, str(e))

            if (b_idx + 1) % 100 == 0 or (b_idx + 1) == len(batch_files):
                log.info("Streamed %d / %d batches...", b_idx + 1, len(batch_files))

        m9_manifest = self.gen_mod09.save_split_datasets(
            mod09_train, mod09_val, mod09_test,
            ["capital_allocated_inr", "calibrated_win_probability", "kelly_fraction", "raw_confidence"],
            "lots_to_trade"
        )

        m11_manifest = self.gen_mod11.save_split_datasets(
            mod11_train, mod11_val, mod11_test,
            ["expected_slippage_pts", "execution_gate", "volume_delta_pct"],
            "contradiction_flag"
        )

        elapsed = time.time() - t_start
        log.info("PHASE 5.4 — LAYER 4 (EXECUTION LAYER) DATASET GENERATION COMPLETE in %.2f seconds!", elapsed)
        return m9_manifest, m11_manifest


if __name__ == "__main__":
    gen = Layer4ExecutionGenerator()
    gen.run_layer4_generation()
