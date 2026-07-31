"""
Phase 2.1 — Historical Replay Engine (1000+ Situations)
Executes historical replay across canonical market snapshots, generates 1000+ Decision Support
Assessments, saves immutable audit packages, and logs empirical validation metrics.

📜 THE ESSENCE:
"Evidence first. Conclusions second."
"Explain every assessment with evidence, uncertainty, and traceability."
"""

import os
import sys
import glob
import json
import logging
from typing import Dict, Any, List

import pyarrow.parquet as pq

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.memory.ranker import MemoryRankerEngine
from app.synthesis.engine import ExperienceSynthesisEngine
from app.reasoning.engine import CognitiveReasoningEngine
from app.decision.engine import DecisionSupportEngine

SIT_STORE_DIR = "E:/Future Stock/research_storage/situation_store/exchange=NSE_FO"
REPLAY_STORAGE_DIR = "E:/Future Stock/research_storage/replay_audit_packages"
QUALITY_REPORTS_DIR = "E:/Future Stock/research_storage/quality_reports"
os.makedirs(REPLAY_STORAGE_DIR, exist_ok=True)
os.makedirs(QUALITY_REPORTS_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("phase_2_replay_engine")

class Phase2HistoricalReplayEngine:
    """
    Executes Phase 2.1 Historical Replay across 1000+ market situations.
    """

    def __init__(self):
        self.ranker = MemoryRankerEngine()
        self.synthesizer = ExperienceSynthesisEngine()
        self.reasoning_engine = CognitiveReasoningEngine()
        self.decision_engine = DecisionSupportEngine()

    def _get_item(self, data_dict: dict, key: str, idx: int, default_val: Any = "") -> Any:
        val_list = data_dict.get(key)
        if val_list is not None and len(val_list) > idx:
            return val_list[idx]
        return default_val

    def run_replay(self, max_cases: int = 1000) -> Dict[str, Any]:
        log.info("=" * 70)
        log.info("STARTING PHASE 2.1 HISTORICAL REPLAY ENGINE (Limit: %d cases)", max_cases)
        log.info("=" * 70)

        parts = glob.glob(os.path.join(SIT_STORE_DIR, "**", "*.parquet"), recursive=True)
        log.info("Found %d partition files in Situation Store.", len(parts))

        replayed_count = 0
        traceability_failures = 0
        readiness_counts = {"LOW": 0, "MODERATE": 0, "HIGH": 0}
        total_unknown_coverage = 0.0
        total_confidence = 0.0
        contradiction_counts = 0

        audit_packages_saved = []
        cases_per_partition = max(1, (max_cases // len(parts)) + 2)

        for p_file in parts:
            if replayed_count >= max_cases:
                break

            try:
                tbl = pq.ParquetFile(p_file).read()
                dict_data = tbl.to_pydict()
                num_rows = tbl.num_rows
            except Exception as e:
                log.warning("Could not read partition %s: %s", p_file, str(e))
                continue

            step = max(1, num_rows // cases_per_partition)
            indices = [i for i in range(0, num_rows, step)[:cases_per_partition] if i < num_rows]

            for idx in indices:
                if replayed_count >= max_cases:
                    break

                try:
                    sym = self._get_item(dict_data, "symbol", idx, "NIFTY")
                    ex = "NSE"
                    ts = self._get_item(dict_data, "timestamp", idx, "2026-07-01T03:45:00Z")

                    sit_id = self._get_item(dict_data, "situation_id", idx, "")
                    if not sit_id:
                        sit_id = self._get_item(dict_data, "primary_situation", idx, "SIT_CONSOLIDATION_COMPRESSION")

                    unknowns_raw = self._get_item(dict_data, "unknowns_json", idx, "[]")
                    unknowns_list = json.loads(unknowns_raw) if isinstance(unknowns_raw, str) else list(unknowns_raw)

                    ctx_raw = self._get_item(dict_data, "market_context_json", idx, "{}")
                    ctx_dict = json.loads(ctx_raw) if isinstance(ctx_raw, str) else dict(ctx_raw)

                    trend = ctx_dict.get("trend", "SIDEWAYS_FLAT")
                    vol = ctx_dict.get("volatility", "STABLE")
                    part = ctx_dict.get("participation", "MODERATE")
                    struct = ctx_dict.get("structure", "CONSOLIDATION")
                    pcr_val = float(ctx_dict.get("pcr_oi", 1.0))

                    sev_raw = self._get_item(dict_data, "severity_level", idx, 3)
                    sev_val = int(sev_raw) if sev_raw != "" else 3

                    sit = {
                        "symbol": sym,
                        "exchange": ex,
                        "timestamp": ts,
                        "situation_id": sit_id,
                        "unknowns": unknowns_list,
                        "features": {
                            "trend": trend,
                            "volatility": vol,
                            "participation": part,
                            "structure": struct,
                            "pcr_oi": pcr_val,
                            "severity_level": sev_val
                        }
                    }

                    res = self.ranker.retrieve_and_rank(sit, policy_name="DEFAULT", top_k=10)
                    mems = res.get("top_ranked_memories", [])

                    synth = self.synthesizer.synthesize_experience(sit, mems)
                    synth_dict = synth.to_dict()

                    reasoning = self.reasoning_engine.generate_reasoning_chain(synth_dict)
                    reasoning_dict = reasoning.to_dict()

                    decision = self.decision_engine.generate_decision_support(reasoning_dict, synth_dict)
                    ds_dict = decision.to_dict()

                    tr = ds_dict.get("traceability", {})
                    if not (tr.get("tier_5_assessment_id") and tr.get("tier_4_reasoning_id") and tr.get("tier_3_synthesis_id")):
                        traceability_failures += 1

                    readiness = ds_dict.get("execution_readiness", "LOW")
                    readiness_counts[readiness] += 1

                    total_unknown_coverage += synth_dict["unknowns_assessment"]["unknown_coverage_pct"]
                    total_confidence += ds_dict["evidence_quality_confidence"]

                    if synth_dict["contradiction_summary"].get("contradicting_memories_count", 0) > 0:
                        contradiction_counts += 1

                    replayed_count += 1

                    if replayed_count % 100 == 0:
                        log.info("Replayed %d / %d cases...", replayed_count, max_cases)

                        ap_file = os.path.join(REPLAY_STORAGE_DIR, f"audit_{ds_dict['assessment_id']}.json")
                        with open(ap_file, "w", encoding="utf-8") as f:
                            json.dump(ds_dict["audit_package"], f, indent=2)
                        audit_packages_saved.append(ap_file)

                except Exception as e:
                    log.warning("Replay exception at index %d in %s: %s", idx, p_file, str(e))
                    continue

        avg_unknown_cov = round(total_unknown_coverage / max(1, replayed_count), 2)
        avg_confidence = round(total_confidence / max(1, replayed_count), 2)

        summary = {
            "phase": "Phase 2.1 — Historical Replay",
            "status": "COMPLETED",
            "total_replayed_cases": replayed_count,
            "traceability_failures": traceability_failures,
            "readiness_distribution": readiness_counts,
            "avg_unknown_coverage_pct": f"{avg_unknown_cov}%",
            "avg_evidence_confidence_pct": f"{avg_confidence}%",
            "cases_with_contradictions": contradiction_counts,
            "saved_audit_package_samples": len(audit_packages_saved)
        }

        report_path = os.path.join(QUALITY_REPORTS_DIR, "phase_2_historical_replay_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        log.info("=" * 70)
        log.info("PHASE 2.1 HISTORICAL REPLAY COMPLETE | Total Cases: %d", replayed_count)
        log.info("Traceability Failures      : %d (Target: 0)", traceability_failures)
        log.info("Readiness Distribution     : %s", readiness_counts)
        log.info("Avg Evidence Confidence    : %s%%", avg_confidence)
        log.info("Report Saved               : %s", report_path)
        log.info("=" * 70)

        return summary

if __name__ == "__main__":
    replay_engine = Phase2HistoricalReplayEngine()
    replay_engine.run_replay(max_cases=1000)
