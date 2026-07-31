"""
Phase 2.2 — Fast Scientific Behavior Profile Analytics Suite
Pre-caches memory store into RAM for high-speed execution across 1,000 cases.
Generates 4 Quantitative Scientific Reports:
1. Report A: Confidence Calibration & Distribution Report (Histogram, Percentiles, Median).
2. Report B: Unknown Source Taxonomy Report (Missing data sources frequency & severity).
3. Report C: Contradiction Taxonomy & Failure Cluster Report (Top failure modes frequency).
4. Report D: Readiness Attribution Report (Root-cause contribution breakdown for LOW readiness).

📜 THE ESSENCE:
"Evidence first. Conclusions second."
"""

import os
import sys
import glob
import json
import logging
from typing import Dict, Any, List
from collections import Counter
import statistics

import pyarrow.parquet as pq

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.memory.ranker import MemoryRankerEngine
from app.synthesis.engine import ExperienceSynthesisEngine
from app.reasoning.engine import CognitiveReasoningEngine
from app.decision.engine import DecisionSupportEngine

SIT_STORE_DIR = "E:/Future Stock/research_storage/situation_store/exchange=NSE_FO"
QUALITY_REPORTS_DIR = "E:/Future Stock/research_storage/quality_reports"
os.makedirs(QUALITY_REPORTS_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("phase_2_2_analytics")

def _safe_get(data_dict: dict, key: str, idx: int, default_val: Any = "") -> Any:
    arr = data_dict.get(key)
    if arr is not None and isinstance(arr, (list, tuple)) and idx < len(arr):
        return arr[idx]
    return default_val

def run_phase_2_2_analytics(sample_size: int = 1000) -> Dict[str, Any]:
    log.info("=" * 70)
    log.info("STARTING PHASE 2.2 SCIENTIFIC BEHAVIOR PROFILE ANALYTICS (N=%d)", sample_size)
    log.info("=" * 70)

    ranker = MemoryRankerEngine()
    synthesizer = ExperienceSynthesisEngine()
    reasoning_engine = CognitiveReasoningEngine()
    decision_engine = DecisionSupportEngine()

    # Pre-load all memory partition files into ranker cache
    mem_parts = glob.glob("E:/Future Stock/research_storage/memory_store/**/*.parquet", recursive=True)
    log.info("Pre-loading %d memory store partitions into memory...", len(mem_parts))

    for m_file in mem_parts:
        if m_file not in ranker._partition_cache:
            try:
                tbl = pq.ParquetFile(m_file).read()
                dict_data = tbl.to_pydict()
                part_recs = []
                for i in range(tbl.num_rows):
                    part_recs.append({
                        "memory_id": dict_data["memory_id"][i],
                        "primary_situation": dict_data["primary_situation"][i],
                        "symbol": dict_data["symbol"][i],
                        "start_time": dict_data["start_time"][i],
                        "duration_minutes": dict_data["duration_minutes"][i],
                        "features": json.loads(dict_data["features_json"][i]),
                        "episode_outcomes": json.loads(dict_data["episode_outcomes_json"][i])
                    })
                ranker._partition_cache[m_file] = part_recs
            except Exception:
                continue

    log.info("Memory store pre-cached! Analyzing 1,000 cases...")

    parts = glob.glob(os.path.join(SIT_STORE_DIR, "**", "*.parquet"), recursive=True)
    cases_per_partition = max(1, (sample_size // len(parts)) + 2)

    confidence_scores = []
    unknown_sources_counter = Counter()
    failure_clusters_counter = Counter()
    readiness_root_cause = Counter()

    replayed_count = 0

    for p_file in parts:
        if replayed_count >= sample_size:
            break

        try:
            tbl = pq.ParquetFile(p_file).read()
            dict_data = tbl.to_pydict()
            num_rows = tbl.num_rows
        except Exception:
            continue

        step = max(1, num_rows // cases_per_partition)
        indices = [i for i in range(0, num_rows, step)[:cases_per_partition] if i < num_rows]

        for idx in indices:
            if replayed_count >= sample_size:
                break

            try:
                sym = _safe_get(dict_data, "symbol", idx, "NIFTY")
                ts = _safe_get(dict_data, "timestamp", idx, "2026-07-01T03:45:00Z")
                sit_id = _safe_get(dict_data, "situation_id", idx, "")
                if not sit_id:
                    sit_id = _safe_get(dict_data, "primary_situation", idx, "SIT_CONSOLIDATION_COMPRESSION")

                unknowns_raw = _safe_get(dict_data, "unknowns_json", idx, "[]")
                unknowns_list = json.loads(unknowns_raw) if isinstance(unknowns_raw, str) else list(unknowns_raw)

                ctx_raw = _safe_get(dict_data, "market_context_json", idx, "{}")
                ctx_dict = json.loads(ctx_raw) if isinstance(ctx_raw, str) else dict(ctx_raw)

                trend = ctx_dict.get("trend", "SIDEWAYS_FLAT")
                vol = ctx_dict.get("volatility", "STABLE")
                part = ctx_dict.get("participation", "MODERATE")
                struct = ctx_dict.get("structure", "CONSOLIDATION")
                pcr_val = float(ctx_dict.get("pcr_oi", 1.0))

                sev_raw = _safe_get(dict_data, "severity_level", idx, 3)
                sev_val = int(sev_raw) if sev_raw != "" else 3

                sit = {
                    "symbol": sym,
                    "exchange": "NSE",
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

                res = ranker.retrieve_and_rank(sit, policy_name="DEFAULT", top_k=10)
                mems = res.get("top_ranked_memories", [])

                synth = synthesizer.synthesize_experience(sit, mems)
                synth_dict = synth.to_dict()

                reasoning = reasoning_engine.generate_reasoning_chain(synth_dict)
                reasoning_dict = reasoning.to_dict()

                decision = decision_engine.generate_decision_support(reasoning_dict, synth_dict)
                ds_dict = decision.to_dict()

                # Collect Metrics for Analytics Reports
                conf = ds_dict["evidence_quality_confidence"]
                confidence_scores.append(conf)

                # Report B: Unknown Sources
                for u_item in ds_dict["information_gap"]["missing_information"]:
                    unknown_sources_counter[u_item] += 1

                # Report C: Failure Clusters
                ca = synth_dict["contradiction_summary"]
                cluster_name = ca.get("largest_failure_cluster", "NONE_DETECTED")
                if cluster_name:
                    failure_clusters_counter[cluster_name] += 1

                # Report D: Readiness Attribution Root Causes
                if ds_dict["execution_readiness"] == "LOW":
                    if len(mems) < 15:
                        readiness_root_cause["Low Sample Size (N < 15)"] += 1
                    elif conf < 50.0:
                        readiness_root_cause["Low Evidence Confidence (< 50%)"] += 1
                    elif ca.get("contradicting_memories_count", 0) > 3:
                        readiness_root_cause["High Contradictions (> 3)"] += 1
                    else:
                        readiness_root_cause["Information Gap Constraints"] += 1

                replayed_count += 1

                if replayed_count % 200 == 0:
                    log.info("Analyzed %d / %d cases...", replayed_count, sample_size)

            except Exception as e:
                continue

    # ── REPORT A: CONFIDENCE CALIBRATION & HISTOGRAM ─────────────────────────
    bands = {"0-10%": 0, "10-20%": 0, "20-30%": 0, "30-50%": 0, "50%+": 0}
    for c in confidence_scores:
        if c < 10.0:
            bands["0-10%"] += 1
        elif c < 20.0:
            bands["10-20%"] += 1
        elif c < 30.0:
            bands["20-30%"] += 1
        elif c < 50.0:
            bands["30-50%"] += 1
        else:
            bands["50%+"] += 1

    report_a = {
        "sample_size": len(confidence_scores),
        "mean_confidence_pct": round(statistics.mean(confidence_scores), 2) if confidence_scores else 0.0,
        "median_confidence_pct": round(statistics.median(confidence_scores), 2) if confidence_scores else 0.0,
        "min_confidence_pct": round(min(confidence_scores), 2) if confidence_scores else 0.0,
        "max_confidence_pct": round(max(confidence_scores), 2) if confidence_scores else 0.0,
        "stdev_confidence": round(statistics.stdev(confidence_scores), 2) if len(confidence_scores) > 1 else 0.0,
        "histogram_distribution": bands
    }

    # ── REPORT B: UNKNOWN SOURCE TAXONOMY ────────────────────────────────────
    report_b = {
        "missing_source_frequency": dict(unknown_sources_counter.most_common()),
        "top_information_bottleneck": unknown_sources_counter.most_common(1)[0][0] if unknown_sources_counter else "None"
    }

    # ── REPORT C: CONTRADICTION TAXONOMY ─────────────────────────────────────
    report_c = {
        "failure_cluster_frequency": dict(failure_clusters_counter.most_common()),
        "top_failure_mode": failure_clusters_counter.most_common(1)[0][0] if failure_clusters_counter else "None"
    }

    # ── REPORT D: READINESS ATTRIBUTION BREAKDOWN ────────────────────────────
    total_low = sum(readiness_root_cause.values())
    report_d = {
        "total_low_readiness_cases": total_low,
        "root_cause_contribution_pct": {
            k: f"{round((v / max(1, total_low)) * 100.0, 1)}% ({v} cases)"
            for k, v in readiness_root_cause.most_common()
        }
    }

    full_behavior_profile = {
        "sprint": "Phase 2.2 — Scientific Behavior Profile & Calibration Analytics",
        "sample_size": replayed_count,
        "report_A_confidence_calibration": report_a,
        "report_B_unknown_source_taxonomy": report_b,
        "report_C_contradiction_taxonomy": report_c,
        "report_D_readiness_attribution": report_d
    }

    report_path = os.path.join(QUALITY_REPORTS_DIR, "phase_2_2_behavior_profile_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(full_behavior_profile, f, indent=2)

    log.info("=" * 70)
    log.info("PHASE 2.2 BEHAVIOR PROFILE REPORT GENERATED SUCCESSFULLY")
    log.info("Total Cases Analyzed : %d", replayed_count)
    log.info("Median Confidence    : %s%%", report_a["median_confidence_pct"])
    log.info("Top Unknown Gap      : %s", report_b["top_information_bottleneck"])
    log.info("Top Failure Mode     : %s", report_c["top_failure_mode"])
    log.info("Report Saved         : %s", report_path)
    log.info("=" * 70)

    return full_behavior_profile

if __name__ == "__main__":
    run_phase_2_2_analytics(sample_size=1000)
