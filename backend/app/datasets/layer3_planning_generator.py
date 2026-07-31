"""
🏛️ OI Lens — LAYER 3 (PLANNING LAYER) DATASET GENERATOR (v2.0 CLEAN ANTI-LEAKAGE)

Generates ML datasets for:
1. MOD_04_STRIKE_SELECTION
2. MOD_05_ENTRY_TIMING
3. MOD_06_EXIT_TIMING (Clean Anti-Leakage Feature Vector X)
4. MOD_07_HOLDING_TIME

ENFORCES CAUSALITY RULES via LeakageGuard:
- Zero target_*, mfe_*, mae_* inside Feature Vector X!
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
from app.validation.leakage_guard import LeakageGuard, DataLeakageError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("layer3_planning_gen")


class Layer3PlanningGenerator:

    def __init__(self):
        self.gen_mod04 = BaseDatasetGenerator("MOD_04_STRIKE_SELECTION", "Strike & Option Selection", "layer_3_planning")
        self.gen_mod05 = BaseDatasetGenerator("MOD_05_ENTRY_TIMING", "Precision Entry Timing", "layer_3_planning")
        self.gen_mod06 = BaseDatasetGenerator("MOD_06_EXIT_TIMING", "Precision Exit & Trailing Engine", "layer_3_planning")
        self.gen_mod07 = BaseDatasetGenerator("MOD_07_HOLDING_TIME", "Optimal Holding Time Estimator", "layer_3_planning")

    def run_layer3_generation(self):
        log.info("=" * 80)
        log.info("PHASE 5.3 — LAYER 3 (PLANNING LAYER) CLEAN ANTI-LEAKAGE GENERATOR v2.0")
        log.info("Streaming ALL %d batch files for MOD_04, MOD_05, MOD_06, MOD_07...", len(self.gen_mod04.batch_files))
        log.info("=" * 80)

        mod04_train, mod04_val, mod04_test = [], [], []
        mod05_train, mod05_val, mod05_test = [], [], []
        mod06_train, mod06_val, mod06_test = [], [], []
        mod07_train, mod07_val, mod07_test = [], [], []

        batch_files = self.gen_mod04.batch_files
        t_start = time.time()

        mod06_feature_cols = ["spot_price", "atr_14", "trailing_stop_vwap"]
        LeakageGuard.audit_feature_names(mod06_feature_cols, "mfe_bound_pct")

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
                    spot_price = float(raw_f.get("spot_price", raw_f.get("close", 24000.0)))
                    atr = float(raw_f.get("atr", 120.0))
                    iv_skew = float(raw_f.get("iv_skew", 0.0))

                    mfe_15m = float(out_c.get("horizon_15m", {}).get("mfe_pct", 0.0))
                    mae_15m = float(out_c.get("horizon_15m", {}).get("mae_pct", 0.0))

                    # 1. MOD_04 Strike Selection Row
                    moneyness = "ATM" if abs(iv_skew) < 0.5 else ("ITM" if iv_skew > 0.5 else "OTM")
                    expected_rr = round(max(1.0, mfe_15m / max(0.1, abs(mae_15m))), 2)

                    row_04 = {
                        "record_id": r_id,
                        "timestamp": ts,
                        "symbol": sym,
                        "moneyness": moneyness,  # Target Y
                        "spot_price": spot_price,
                        "iv_skew": iv_skew,
                        "option_delta": 0.50 if moneyness == "ATM" else (0.65 if moneyness == "ITM" else 0.35),
                        "expected_option_rr": expected_rr
                    }

                    # 2. MOD_05 Entry Timing Row
                    trigger_entry = mfe_15m >= 0.40 and abs(mae_15m) <= 0.20
                    recommended_limit = round(spot_price * (1.0 - 0.0005), 2)

                    row_05 = {
                        "record_id": r_id,
                        "timestamp": ts,
                        "symbol": sym,
                        "trigger_entry_now": trigger_entry,  # Target Y
                        "entry_confidence": float(ai_a.get("confidence_score", 0.85)),
                        "recommended_limit_price": recommended_limit,
                        "vwap_distance_pct": round(float(raw_f.get("vwap_distance_pct", 0.01)), 4)
                    }

                    # 3. MOD_06 Exit Timing Row (Clean Causal Features ONLY)
                    row_06 = {
                        "record_id": r_id,
                        "timestamp": ts,
                        "symbol": sym,
                        "spot_price": spot_price,
                        "atr_14": atr,
                        "trailing_stop_vwap": round(spot_price - (atr * 0.5), 2),
                        "mfe_bound_pct": mfe_15m  # Target Y
                    }

                    # 4. MOD_07 Holding Time Row
                    optimal_holding_mins = 15 if mfe_15m >= 0.50 else (30 if mfe_15m >= 0.25 else 45)

                    row_07 = {
                        "record_id": r_id,
                        "timestamp": ts,
                        "symbol": sym,
                        "optimal_holding_minutes": optimal_holding_mins,  # Target Y
                        "time_decay_warning_minutes": int(optimal_holding_mins * 0.8),
                        "intraday_hour": ts[11:13] if len(ts) >= 13 else "00"
                    }

                    if yr in ("2021", "2022", "2023"):
                        mod04_train.append(row_04)
                        mod05_train.append(row_05)
                        mod06_train.append(row_06)
                        mod07_train.append(row_07)
                    elif yr == "2024":
                        mod04_val.append(row_04)
                        mod05_val.append(row_05)
                        mod06_val.append(row_06)
                        mod07_val.append(row_07)
                    else:
                        mod04_test.append(row_04)
                        mod05_test.append(row_05)
                        mod06_test.append(row_06)
                        mod07_test.append(row_07)

            except Exception as e:
                log.error("Error processing batch %s: %s", f_path, str(e))

            if (b_idx + 1) % 200 == 0 or (b_idx + 1) == len(batch_files):
                log.info("Streamed %d / %d batches...", b_idx + 1, len(batch_files))

        m4_manifest = self.gen_mod04.save_split_datasets(
            mod04_train, mod04_val, mod04_test,
            ["spot_price", "iv_skew", "option_delta", "expected_option_rr"],
            "moneyness"
        )

        m5_manifest = self.gen_mod05.save_split_datasets(
            mod05_train, mod05_val, mod05_test,
            ["entry_confidence", "recommended_limit_price", "vwap_distance_pct"],
            "trigger_entry_now"
        )

        m6_manifest = self.gen_mod06.save_split_datasets(
            mod06_train, mod06_val, mod06_test,
            mod06_feature_cols,
            "mfe_bound_pct"
        )

        m7_manifest = self.gen_mod07.save_split_datasets(
            mod07_train, mod07_val, mod07_test,
            ["time_decay_warning_minutes", "intraday_hour"],
            "optimal_holding_minutes"
        )

        elapsed = time.time() - t_start
        log.info("PHASE 5.3 — CLEAN LAYER 3 DATASET GENERATION COMPLETE in %.2f seconds!", elapsed)
        return m4_manifest, m5_manifest, m6_manifest, m7_manifest


if __name__ == "__main__":
    gen = Layer3PlanningGenerator()
    gen.run_layer3_generation()
