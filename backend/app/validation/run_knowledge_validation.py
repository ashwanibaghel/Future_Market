"""
🚨 OI Lens — STEP 4.5 & 4.6 KNOWLEDGE VALIDATION & STABILITY ENGINE (v2.0)

GRANULAR HYPOTHESIS EXPANSION + RESEARCH-GRADE VALIDATION:
1. Granular Hypothesis Generator: Multi-dimensional combinations yielding hundreds of hypotheses.
2. Baselines, Relative Risk (RR), Odds Ratio (OR), Wilson 95% CIs, Chi-Square (chi2), FDR (Benjamini-Hochberg).
3. Replication Protocol: Discovery Window (2021-2024) vs Validation Window (2025-2026).
4. Multi-Year Stability Scoring (0-100).
5. Operational Readiness Tagging: PRODUCTION_READY, SHADOW_READY, EXPERIMENTAL, RESEARCH_ONLY.
6. 100% Dynamic configuration via `knowledge_config.yaml`.
7. Evidence Lineage (sample_evidence_ids) saved physically in Parquet.
"""

import os
import sys
import glob
import json
import time
import math
import yaml
import logging
from typing import Dict, Any, List, Tuple
from collections import Counter, defaultdict

import numpy as np
import scipy.stats as stats
import pyarrow as pa
import pyarrow.parquet as pq

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("knowledge_validation_v2")

# Load Config
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "knowledge_config.yaml")
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        CFG = yaml.safe_load(f)
else:
    CFG = {
        "minimum_sample_size": 30,
        "minimum_support_pct": 2.0,
        "minimum_confidence_pct": 55.0,
        "fdr_alpha": 0.05,
        "p_value_alpha": 0.05,
        "confidence_interval_method": "wilson",
        "discovery_window_years": ["2021", "2022", "2023", "2024"],
        "validation_window_years": ["2025", "2026"],
        "dataset_version": "v1.0-evidence",
        "input_dataset_dir": "E:/Future Stock/research_storage/market_intelligence_dataset",
        "output_knowledge_dir": "E:/Future Stock/research_storage/knowledge_base/v1",
        "output_validation_dir": "E:/Future Stock/research_storage/knowledge_base/v1/validation",
        "reports_dir": "E:/Future Stock/research_storage/quality_reports",
    }

INPUT_DATASET_DIR = CFG["input_dataset_dir"]
OUTPUT_KNOWLEDGE_DIR = CFG["output_knowledge_dir"]
OUTPUT_VALIDATION_DIR = CFG["output_validation_dir"]
REPORTS_DIR = CFG["reports_dir"]

os.makedirs(OUTPUT_KNOWLEDGE_DIR, exist_ok=True)
os.makedirs(OUTPUT_VALIDATION_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)


# ── STATISTICAL UTILITIES ───────────────────────────────────────────────────

def wilson_score_interval(k: int, n: int, confidence: float = 0.95) -> Tuple[float, float]:
    """Calculates Wilson Score Binomial 95% Confidence Interval [lower, upper] in %."""
    if n <= 0:
        return 0.0, 0.0
    p_hat = k / n
    z = stats.norm.ppf(1 - (1 - confidence) / 2)  # 1.96 for 95%
    denom = 1 + (z ** 2) / n
    center = (p_hat + (z ** 2) / (2 * n)) / denom
    margin = (z * math.sqrt((p_hat * (1 - p_hat) + (z ** 2) / (4 * n)) / n)) / denom
    lower = max(0.0, (center - margin) * 100.0)
    upper = min(100.0, (center + margin) * 100.0)
    return round(lower, 2), round(upper, 2)


def compute_chi2_pvalue(obs_pos: int, obs_neg: int, base_pos_rate: float) -> Tuple[float, float]:
    """Calculates Chi-Square test statistic and raw p-value against baseline rate."""
    n = obs_pos + obs_neg
    if n <= 0 or base_pos_rate <= 0 or base_pos_rate >= 1:
        return 0.0, 1.0
    exp_pos = n * base_pos_rate
    exp_neg = n * (1 - base_pos_rate)

    if exp_pos < 1 or exp_neg < 1:
        return 0.0, 1.0

    chi2 = ((obs_pos - exp_pos) ** 2) / exp_pos + ((obs_neg - exp_neg) ** 2) / exp_neg
    p_val = float(stats.chi2.sf(chi2, df=1))
    return round(float(chi2), 3), float(p_val)


def benjamini_hochberg_correction(p_values: List[float], alpha: float = 0.05) -> Tuple[List[float], List[bool]]:
    """Applies Benjamini-Hochberg False Discovery Rate (FDR) adjustment."""
    m = len(p_values)
    if m == 0:
        return [], []

    sorted_indices = np.argsort(p_values)
    sorted_p = np.array(p_values)[sorted_indices]

    adjusted_p = np.zeros(m)
    cum_min = 1.0
    for i in range(m - 1, -1, -1):
        rank = i + 1
        adj = (sorted_p[i] * m) / rank
        cum_min = min(cum_min, adj)
        adjusted_p[i] = min(1.0, cum_min)

    orig_adj_p = np.zeros(m)
    orig_adj_p[sorted_indices] = adjusted_p
    fdr_passed = [adj_p <= alpha for adj_p in orig_adj_p]

    return orig_adj_p.tolist(), fdr_passed


def compute_stability_score(year_rates: List[float]) -> float:
    """Calculates stability score (0-100) based on coefficient of variation across years."""
    valid_rates = [r for r in year_rates if r > 0]
    if len(valid_rates) <= 1:
        return 50.0
    mean_val = np.mean(valid_rates)
    std_val = np.std(valid_rates)
    if mean_val <= 0:
        return 0.0
    cv = std_val / mean_val
    stability = max(0.0, 100.0 * (1.0 - cv))
    return round(float(stability), 1)


# ── MAIN VALIDATION ENGINE V2 ───────────────────────────────────────────────

class KnowledgeValidationEngineV2:

    def __init__(self):
        self.batch_files = sorted(glob.glob(os.path.join(INPUT_DATASET_DIR, "*.parquet")))
        self.total_records = 0
        self.know_counter = 1

        # Global Baselines Accumulators per horizon
        self.global_total = 0
        self.horizon_pos_totals = Counter()
        self.symbol_totals = Counter()
        self.symbol_pos_totals = defaultdict(Counter)

        # Multi-Dimensional Granular Hypotheses Accumulator
        # Key: (category, condition_key, target_horizon, target_outcome_type)
        self.hypothesis_counts = defaultdict(lambda: {
            "disc_total": 0, "disc_pos": 0,
            "val_total": 0, "val_pos": 0,
            "yearly_pos": defaultdict(int),
            "yearly_total": defaultdict(int),
            "symbol_pos": defaultdict(int),
            "symbol_total": defaultdict(int),
            "sample_record_ids": []
        })

        self.rare_events_store = []

    def generate_know_id(self) -> str:
        kid = f"KNOW_{self.know_counter:06d}"
        self.know_counter += 1
        return kid

    def stream_and_accumulate_data(self):
        log.info("=" * 80)
        log.info("STEP 4.5 & 4.6 — KNOWLEDGE VALIDATION & STABILITY ENGINE v2.0")
        log.info("Executing Granular Multi-Dimensional Hypothesis Mining over %d batch files...", len(self.batch_files))
        log.info("Discovery Window: %s | Validation Window: %s", CFG["discovery_window_years"], CFG["validation_window_years"])
        log.info("=" * 80)

        disc_years = set(CFG["discovery_window_years"])
        val_years = set(CFG["validation_window_years"])
        t_start = time.time()

        for b_idx, f_path in enumerate(self.batch_files):
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
                    hr = ts[11:13] if len(ts) >= 13 else "00"

                    raw_f = json.loads(raw_facts_json[i]) if isinstance(raw_facts_json[i], str) else raw_facts_json[i]
                    ai_a = json.loads(ai_assess_json[i]) if isinstance(ai_assess_json[i], str) else ai_assess_json[i]
                    out_c = json.loads(outcomes_json[i]) if isinstance(outcomes_json[i], str) else outcomes_json[i]

                    sym = raw_f.get("symbol", "NIFTY")
                    sit_id = ai_a.get("situation_id", "SIT_CONSOLIDATION_COMPRESSION")
                    trend = raw_f.get("trend", "SIDEWAYS_FLAT")
                    vol = raw_f.get("volatility", "STABLE")
                    part = raw_f.get("participation", "MODERATE")
                    struct = raw_f.get("structure", "CONSOLIDATION")
                    sev = int(raw_f.get("severity_level", 3))

                    regime_str = f"{trend}|{vol}|{struct}"

                    # Multi-Horizon Directional Evaluation
                    horizon_positive = {}
                    for h_name in ["horizon_5m", "horizon_15m", "horizon_30m", "horizon_60m", "horizon_eod"]:
                        h_data = out_c.get(h_name, {})
                        mfe = float(h_data.get("mfe_pct", 0.0))
                        mae = float(h_data.get("mae_pct", 0.0))
                        horizon_positive[h_name] = mfe > abs(mae)

                    self.global_total += 1
                    self.symbol_totals[sym] += 1
                    for h_name, is_pos in horizon_positive.items():
                        if is_pos:
                            self.horizon_pos_totals[h_name] += 1
                            self.symbol_pos_totals[sym][h_name] += 1

                    # Helper to accumulate hypothesis
                    def add_hyp(cat: str, key: str, horiz: str, is_positive_event: bool, outcome_type: str = "POSITIVE_OUTCOME"):
                        hk = (cat, key, horiz, outcome_type)
                        h_entry = self.hypothesis_counts[hk]
                        is_disc = yr in disc_years

                        if is_disc:
                            h_entry["disc_total"] += 1
                            if is_positive_event: h_entry["disc_pos"] += 1
                        else:
                            h_entry["val_total"] += 1
                            if is_positive_event: h_entry["val_pos"] += 1

                        h_entry["yearly_total"][yr] += 1
                        if is_positive_event: h_entry["yearly_pos"][yr] += 1
                        h_entry["symbol_total"][sym] += 1
                        if is_positive_event: h_entry["symbol_pos"][sym] += 1

                        if len(h_entry["sample_record_ids"]) < 5:
                            h_entry["sample_record_ids"].append(r_id)

                    # ── GRANULAR HYPOTHESIS MINING ACROSS ALL CROSS-SECTIONS ──
                    for h_name, is_pos in horizon_positive.items():

                        # 1. Situation × Symbol × Horizon
                        add_hyp("SITUATION_SYMBOL_HORIZON", f"{sit_id} @ {sym}", h_name, is_pos)

                        # 2. Situation × Regime × Horizon
                        add_hyp("SITUATION_REGIME_HORIZON", f"{sit_id} in [{regime_str}]", h_name, is_pos)

                        # 3. Situation × Unknown Gap × Horizon
                        gaps = ai_a.get("unknown_information_gaps", [])
                        for g in gaps:
                            add_hyp("UNKNOWN_GAP_RISK", f"{sit_id} + Missing [{g}]", h_name, not is_pos, outcome_type="FAILURE_RISK")

                        # 4. Situation × Contradiction Cluster × Horizon
                        contra = ai_a.get("contradictions_summary", {})
                        if isinstance(contra, dict) and contra.get("largest_failure_cluster"):
                            c_cluster = contra["largest_failure_cluster"]
                            add_hyp("CONTRADICTION_CLUSTER_RISK", f"{sit_id} + Cluster [{c_cluster}]", h_name, not is_pos, outcome_type="FAILURE_RISK")

                        # 5. Severity × Regime × Horizon
                        add_hyp("SEVERITY_REGIME_HORIZON", f"Severity-{sev} in [{regime_str}]", h_name, is_pos)

                        # 6. Participation × Volatility × Horizon
                        add_hyp("FLOW_VOLATILITY_HORIZON", f"{part} Flow in [{vol} Vol]", h_name, is_pos)

                    # 7. Temporal Hour × Situation
                    add_hyp("TEMPORAL_HOURLY", f"Trading Hour {hr}:00 + {sit_id}", "horizon_5m", horizon_positive["horizon_5m"])

                    # 8. Rare Events Preservation (Scale-Corrected)
                    mfe_5m = float(out_c.get("horizon_5m", {}).get("mfe_pct", 0.0))
                    mae_5m = float(out_c.get("horizon_5m", {}).get("mae_pct", 0.0))
                    if abs(mfe_5m) >= 0.80 or abs(mae_5m) >= 0.80 or sev >= 4:
                        if len(self.rare_events_store) < 10000:
                            self.rare_events_store.append({
                                "record_id": r_id,
                                "timestamp": ts,
                                "symbol": sym,
                                "situation_id": sit_id,
                                "regime": regime_str,
                                "mfe_pct_5m": mfe_5m,
                                "mae_pct_5m": mae_5m,
                                "severity_level": sev,
                                "event_category": "EXTREME_EXPANSION" if mfe_5m >= 0.80 else ("SEVERE_DRAWDOWN" if mae_5m <= -0.80 else "HIGH_SEVERITY_STRESS"),
                            })

                    self.total_records += 1

            except Exception as e:
                log.error("Error streaming batch %s: %s", f_path, str(e))

            if (b_idx + 1) % 100 == 0 or (b_idx + 1) == len(self.batch_files):
                elapsed = max(1.0, time.time() - t_start)
                speed = self.total_records / elapsed
                log.info("Processed %d / %d batches (%d records, %.1f rec/sec)...",
                         b_idx + 1, len(self.batch_files), self.total_records, speed)

        log.info("STREAMING & HYPOTHESIS MINING COMPLETE: %d total evidence records, %d candidate hypotheses generated.",
                 self.total_records, len(self.hypothesis_counts))

    # ── STATISTICAL TESTING & OPERATIONAL READINESS ENGINE ───────────────────

    def execute_statistical_validation(self):
        log.info("Executing Statistical Validation & Operational Readiness Pipeline across %d candidate hypotheses...",
                 len(self.hypothesis_counts))

        candidates_data = []
        min_n = CFG["minimum_sample_size"]

        for (cat, key, horiz, outcome_type), h_dict in self.hypothesis_counts.items():
            disc_n = h_dict["disc_total"]
            val_n = h_dict["val_total"]
            tot_n = disc_n + val_n

            if tot_n < min_n:
                continue

            disc_pos = h_dict["disc_pos"]
            val_pos = h_dict["val_pos"]
            tot_pos = disc_pos + val_pos
            tot_neg = tot_n - tot_pos

            # Baseline calculation per horizon
            target_sym = key.split("@")[-1].strip() if "@" in key else "ALL"
            if target_sym in self.symbol_totals and self.symbol_totals[target_sym] > 0:
                p_base = self.symbol_pos_totals[target_sym][horiz] / self.symbol_totals[target_sym]
            else:
                p_base = self.horizon_pos_totals[horiz] / max(1, self.global_total)

            if "FAILURE" in outcome_type:
                p_base = 1.0 - p_base

            p_obs_disc = disc_pos / max(1, disc_n)
            p_obs_val = val_pos / max(1, val_n)
            p_obs_tot = tot_pos / max(1, tot_n)

            # 1. Relative Risk (RR) & Odds Ratio (OR)
            rr = p_obs_tot / max(0.001, p_base)
            odds_obs = p_obs_tot / max(0.001, (1.0 - p_obs_tot))
            odds_base = p_base / max(0.001, (1.0 - p_base))
            odds_ratio = odds_obs / max(0.001, odds_base)

            # 2. 95% Wilson Binomial Confidence Interval
            ci_low, ci_high = wilson_score_interval(tot_pos, tot_n, confidence=0.95)

            # 3. Chi-Square Test & Raw P-Value
            chi2_stat, raw_p = compute_chi2_pvalue(tot_pos, tot_neg, p_base)

            # 4. Replication Status (Discovery 2021-2024 vs Validation 2025-2026)
            rr_disc = p_obs_disc / max(0.001, p_base)
            rr_val = p_obs_val / max(0.001, p_base)

            if disc_n >= 20 and val_n >= 10:
                if (rr_disc >= 1.2 and rr_val >= 1.15) or (rr_disc <= 0.8 and rr_val <= 0.85):
                    repl_status = "REPLICATED"
                elif (rr_disc >= 1.1 and rr_val >= 1.0) or (rr_disc <= 0.9 and rr_val <= 1.0):
                    repl_status = "PARTIALLY_REPLICATED"
                else:
                    repl_status = "FAILED_REPLICATION"
            else:
                repl_status = "INSUFFICIENT_VAL_SAMPLES"

            # 5. Stability Score across years
            yr_rates = [h_dict["yearly_pos"][y] / max(1, h_dict["yearly_total"][y])
                        for y in ["2021", "2022", "2023", "2024", "2025", "2026"]
                        if h_dict["yearly_total"][y] >= 5]
            stability_score = compute_stability_score(yr_rates)

            candidates_data.append({
                "category": cat,
                "condition_key": key,
                "target_horizon": horiz,
                "outcome_type": outcome_type,
                "total_n": tot_n,
                "disc_n": disc_n,
                "val_n": val_n,
                "tot_pos": tot_pos,
                "p_base": round(p_base * 100.0, 2),
                "p_obs_disc": round(p_obs_disc * 100.0, 2),
                "p_obs_val": round(p_obs_val * 100.0, 2),
                "p_obs_tot": round(p_obs_tot * 100.0, 2),
                "relative_risk": round(rr, 2),
                "odds_ratio": round(odds_ratio, 2),
                "ci_lower_pct": ci_low,
                "ci_upper_pct": ci_high,
                "chi2_stat": chi2_stat,
                "raw_p_value": raw_p,
                "replication_status": repl_status,
                "stability_score": stability_score,
                "sample_evidence_ids": ",".join(h_dict["sample_record_ids"])
            })

        # Apply Benjamini-Hochberg FDR Multiple Testing Correction
        raw_p_list = [c["raw_p_value"] for c in candidates_data]
        adj_p_list, fdr_passed_list = benjamini_hochberg_correction(raw_p_list, alpha=CFG["fdr_alpha"])

        validated_repository = []
        baselines_rows = []
        effect_sizes_rows = []
        ci_rows = []
        test_rows = []

        for idx, c in enumerate(candidates_data):
            adj_p = adj_p_list[idx]
            fdr_pass = fdr_passed_list[idx]
            c["adjusted_p_value"] = float(adj_p)
            c["fdr_passed"] = fdr_pass

            know_id = self.generate_know_id()
            c["knowledge_id"] = know_id

            # Validation Decision Matrix (5 Levels)
            rr = c["relative_risk"]
            n = c["total_n"]
            repl = c["replication_status"]
            stab = c["stability_score"]

            if fdr_pass and (rr >= 1.35 or rr <= 0.70) and n >= 80 and repl == "REPLICATED" and stab >= 55:
                decision = "VALIDATED_STRONG"
            elif fdr_pass and (rr >= 1.20 or rr <= 0.82) and n >= 40:
                decision = "VALIDATED_MODERATE"
            elif c["raw_p_value"] <= CFG["p_value_alpha"] and n >= CFG["minimum_sample_size"]:
                decision = "VALIDATED_WEAK"
            elif n < CFG["minimum_sample_size"] or repl == "FAILED_REPLICATION":
                decision = "INCONCLUSIVE"
            else:
                decision = "REFUTED"

            c["validation_decision"] = decision

            # Operational Readiness Level
            if decision == "VALIDATED_STRONG" and repl == "REPLICATED" and stab >= 70:
                op_readiness = "PRODUCTION_READY"
            elif decision in ("VALIDATED_STRONG", "VALIDATED_MODERATE") and repl in ("REPLICATED", "PARTIALLY_REPLICATED"):
                op_readiness = "SHADOW_READY"
            elif decision in ("VALIDATED_MODERATE", "VALIDATED_WEAK"):
                op_readiness = "EXPERIMENTAL"
            else:
                op_readiness = "RESEARCH_ONLY"

            c["operational_readiness"] = op_readiness

            # Quality Score (0-100)
            rel_score = 95.0 if decision == "VALIDATED_STRONG" else (80.0 if decision == "VALIDATED_MODERATE" else 50.0)
            stat_score = min(100.0, max(0.0, (1.0 - adj_p) * 100.0))
            cov_score = min(100.0, (n / self.total_records) * 1000.0)

            w = CFG["quality_weights"]
            overall_quality = round(
                w["reliability"] * rel_score +
                w["statistical_strength"] * stat_score +
                w["stability"] * stab +
                w["reproducibility"] * (90.0 if repl == "REPLICATED" else 50.0) +
                w["coverage"] * cov_score +
                w["novelty"] * 80.0, 1
            )
            c["overall_quality_score"] = overall_quality

            validated_repository.append(c)

            baselines_rows.append({
                "knowledge_id": know_id,
                "category": c["category"],
                "condition_key": c["condition_key"],
                "target_horizon": c["target_horizon"],
                "baseline_probability_pct": c["p_base"],
                "observed_probability_pct": c["p_obs_tot"],
                "sample_size_n": c["total_n"]
            })

            effect_sizes_rows.append({
                "knowledge_id": know_id,
                "condition_key": c["condition_key"],
                "relative_risk": c["relative_risk"],
                "odds_ratio": c["odds_ratio"],
                "risk_multiplier_str": f"{c['relative_risk']}x vs Baseline"
            })

            ci_rows.append({
                "knowledge_id": know_id,
                "condition_key": c["condition_key"],
                "observed_pct": c["p_obs_tot"],
                "ci_95_lower_pct": c["ci_lower_pct"],
                "ci_95_upper_pct": c["ci_upper_pct"],
                "method": CFG["confidence_interval_method"]
            })

            test_rows.append({
                "knowledge_id": know_id,
                "condition_key": c["condition_key"],
                "chi2_stat": c["chi2_stat"],
                "raw_p_value": c["raw_p_value"],
                "adjusted_p_value": c["adjusted_p_value"],
                "fdr_passed": c["fdr_passed"],
                "replication_status": c["replication_status"],
                "stability_score": c["stability_score"],
                "validation_decision": c["validation_decision"],
                "operational_readiness": c["operational_readiness"]
            })

        log.info("FDR Multiple Testing Correction complete: %d hypotheses tested.", len(candidates_data))
        strong_cnt = sum(1 for r in validated_repository if r["validation_decision"] == "VALIDATED_STRONG")
        mod_cnt = sum(1 for r in validated_repository if r["validation_decision"] == "VALIDATED_MODERATE")
        weak_cnt = sum(1 for r in validated_repository if r["validation_decision"] == "VALIDATED_WEAK")
        refuted_cnt = sum(1 for r in validated_repository if r["validation_decision"] == "REFUTED")
        incon_cnt = sum(1 for r in validated_repository if r["validation_decision"] == "INCONCLUSIVE")

        prod_cnt = sum(1 for r in validated_repository if r["operational_readiness"] == "PRODUCTION_READY")
        shadow_cnt = sum(1 for r in validated_repository if r["operational_readiness"] == "SHADOW_READY")

        log.info("Validation Decision Summary:")
        log.info("  🏆 VALIDATED_STRONG   : %d", strong_cnt)
        log.info("  ✅ VALIDATED_MODERATE : %d", mod_cnt)
        log.info("  ⚠️ VALIDATED_WEAK     : %d", weak_cnt)
        log.info("  ❓ INCONCLUSIVE       : %d", incon_cnt)
        log.info("  ❌ REFUTED            : %d", refuted_cnt)
        log.info("Operational Readiness Summary: PRODUCTION_READY=%d | SHADOW_READY=%d", prod_cnt, shadow_cnt)

        # Write Parquet Datasets to v1/validation/
        pq.write_table(pa.Table.from_pylist(baselines_rows), os.path.join(OUTPUT_VALIDATION_DIR, "knowledge_baselines.parquet"), compression="SNAPPY")
        pq.write_table(pa.Table.from_pylist(effect_sizes_rows), os.path.join(OUTPUT_VALIDATION_DIR, "knowledge_effect_sizes.parquet"), compression="SNAPPY")
        pq.write_table(pa.Table.from_pylist(ci_rows), os.path.join(OUTPUT_VALIDATION_DIR, "knowledge_confidence_intervals.parquet"), compression="SNAPPY")
        pq.write_table(pa.Table.from_pylist(test_rows), os.path.join(OUTPUT_VALIDATION_DIR, "knowledge_statistical_tests.parquet"), compression="SNAPPY")
        pq.write_table(pa.Table.from_pylist(validated_repository), os.path.join(OUTPUT_VALIDATION_DIR, "knowledge_validated_repository.parquet"), compression="SNAPPY")

        # Sync master registry
        registry_rows = []
        for r in validated_repository:
            registry_rows.append({
                "knowledge_id": r["knowledge_id"],
                "module": r["category"],
                "title": f"{r['category']}: {r['condition_key']}",
                "hypothesis_statement": f"Condition '{r['condition_key']}' yields {r['p_obs_tot']}% {r['outcome_type']} (RR: {r['relative_risk']}x vs base {r['p_base']}%).",
                "supporting_samples_n": r["tot_pos"],
                "counter_examples_n": r["total_n"] - r["tot_pos"],
                "confidence_pct": r["p_obs_tot"],
                "validation_status": r["validation_decision"],
                "quality_score": r["overall_quality_score"],
                "temporal_stability": "REGIME_SPECIFIC",
                "applicable_symbols": "ALL",
                "dataset_version": CFG.get("dataset_version", "v1.0-evidence"),
            })

        pq.write_table(pa.Table.from_pylist(registry_rows), os.path.join(OUTPUT_KNOWLEDGE_DIR, "knowledge_registry.parquet"), compression="SNAPPY")
        pq.write_table(pa.Table.from_pylist(registry_rows), os.path.join(OUTPUT_KNOWLEDGE_DIR, "knowledge_catalog.parquet"), compression="SNAPPY")
        pq.write_table(pa.Table.from_pylist(self.rare_events_store), os.path.join(OUTPUT_KNOWLEDGE_DIR, "rare_events_knowledge.parquet"), compression="SNAPPY")

        log.info("All Validation & Master Registry Parquet datasets successfully saved to disk!")

        # Build Reports
        self.generate_validation_reports(validated_repository, strong_cnt, mod_cnt, weak_cnt, refuted_cnt, incon_cnt, prod_cnt, shadow_cnt)

    def generate_validation_reports(self, val_repo: List[Dict[str, Any]], strong: int, mod: int, weak: int, refuted: int, incon: int, prod: int, shadow: int):
        log.info("Generating Step 4.5 & 4.6 Dual Validation Reports (Markdown + JSON)...")

        top_validated = sorted([r for r in val_repo if r["validation_decision"] in ("VALIDATED_STRONG", "VALIDATED_MODERATE")], key=lambda x: x["overall_quality_score"], reverse=True)[:50]

        summary_json = {
            "title": "STEP 4.5 & 4.6 — Knowledge Validation & Stability Report (v2.0 Granular)",
            "evidence_dataset_version": CFG.get("dataset_version", "v1.0-evidence"),
            "total_evidence_records_audited": self.total_records,
            "total_hypotheses_tested": len(val_repo),
            "multiple_testing_correction": "Benjamini-Hochberg (FDR)",
            "fdr_alpha": CFG["fdr_alpha"],
            "validation_decision_breakdown": {
                "VALIDATED_STRONG": strong,
                "VALIDATED_MODERATE": mod,
                "VALIDATED_WEAK": weak,
                "INCONCLUSIVE": incon,
                "REFUTED": refuted
            },
            "operational_readiness_breakdown": {
                "PRODUCTION_READY": prod,
                "SHADOW_READY": shadow,
                "EXPERIMENTAL": weak,
                "RESEARCH_ONLY": incon + refuted
            },
            "rare_events_preserved_count": len(self.rare_events_store),
            "top_validated_hypotheses": [
                {
                    "knowledge_id": r["knowledge_id"],
                    "condition": r["condition_key"],
                    "horizon": r["target_horizon"],
                    "outcome": r["outcome_type"],
                    "sample_size_n": r["total_n"],
                    "baseline_pct": r["p_base"],
                    "observed_pct": r["p_obs_tot"],
                    "relative_risk": r["relative_risk"],
                    "ci_95": f"[{r['ci_lower_pct']}%, {r['ci_upper_pct']}%]",
                    "adjusted_p_value": r["adjusted_p_value"],
                    "replication_status": r["replication_status"],
                    "stability_score": r["stability_score"],
                    "validation_decision": r["validation_decision"],
                    "operational_readiness": r["operational_readiness"],
                    "quality_score": r["overall_quality_score"]
                }
                for r in top_validated
            ]
        }

        json_out_path = os.path.join(OUTPUT_VALIDATION_DIR, "knowledge_validation_summary.json")
        with open(json_out_path, "w", encoding="utf-8") as f:
            json.dump(summary_json, f, indent=2)
        log.info("Validation Summary JSON Saved: %s", json_out_path)

        # Markdown Report
        top_table_rows = []
        for r in top_validated[:25]:
            top_table_rows.append(
                f"| `{r['knowledge_id']}` | **{r['condition_key']}** | `{r['target_horizon']}` | {r['total_n']:,} | {r['p_base']}% | **{r['p_obs_tot']}%** | **{r['relative_risk']}x** | `[{r['ci_lower_pct']}%, {r['ci_upper_pct']}%]` | `{r['adjusted_p_value']:.2e}` | `{r['replication_status']}` | **{r['stability_score']}** | `{r['validation_decision']}` | `{r['operational_readiness']}` |"
            )
        table_str = "\n".join(top_table_rows)

        md_report = f"""# STEP 4.5 & 4.6 — Knowledge Validation & Stability Research Report (v2.0 Granular)

> **System Identity**: *Research Paper Grade Statistical Validation Engine*  
> **Input Evidence**: `E:/Future Stock/research_storage/market_intelligence_dataset/` (**`{self.total_records:,}` Records**)  
> **Dataset Version**: `{CFG.get("dataset_version", "v1.0-evidence")}`  
> **Statistical Framework**: **Relative Risk ($RR$), Odds Ratio ($OR$), Wilson 95% CIs, Chi-Square ($\chi^2$), Benjamini-Hochberg FDR Adjustment ($\\alpha=0.05$)**  
> **Replication Protocol**: **Discovery Window (`2021–2024`) vs Validation Window (`2025–2026`)**

---

> 🛑 **CAUSALITY GUARD & SCIENTIFIC INTEGRITY DISCLAIMER**:  
> *Observed associations do not imply causation. These are statistically supported empirical relationships within the analyzed historical dataset (`2021–2026`). Further experimental and live shadow validation is required before treating any relationship as causal.*

---

## 🏛️ EXECUTIVE SUMMARY & HYPOTHESIS FILTRATION METRICS

A total of **`{len(val_repo):,}` candidate hypotheses** were extracted across multi-dimensional cross-sections (`Situation` × `Symbol` × `Regime` × `Gap` × `Contradiction` × `Horizon`). Every hypothesis was stress-tested against global baselines, 95% Wilson binomial confidence intervals, FDR multiple testing correction, temporal replication, and multi-year stability.

### 📊 Validation Decision Matrix Results:

| Validation Decision | Hypotheses Count | Share % | Description & Criteria |
| :--- | :---: | :---: | :--- |
| 🏆 **VALIDATED_STRONG** | **`{strong:,}`** | **`{strong/max(1,len(val_repo))*100:.1f}%`** | FDR passed, $RR \ge 1.35\times$, $N \ge 80$, Replicated in 2025-2026, Stability $\ge 55$ |
| ✅ **VALIDATED_MODERATE** | **`{mod:,}`** | **`{mod/max(1,len(val_repo))*100:.1f}%`** | FDR passed, $RR \ge 1.20\times$, $N \ge 40$ |
| ⚠️ **VALIDATED_WEAK** | **`{weak:,}`** | **`{weak/max(1,len(val_repo))*100:.1f}%`** | Raw $p \le 0.05$, $N \ge 30$, FDR or replication marginal |
| ❓ **INCONCLUSIVE** | **`{incon:,}`** | **`{incon/max(1,len(val_repo))*100:.1f}%`** | Insufficient sample size or inconsistent direction |
| ❌ **REFUTED** | **`{refuted:,}`** | **`{refuted/max(1,len(val_repo))*100:.1f}%`** | Empirical evidence contradicts hypothesis or $RR \approx 1.0\times$ |
| **TOTAL TESTED** | **`{len(val_repo):,}`** | **100.0%** | **Rigorous Knowledge Filtration Complete** |

### 🎯 Operational Readiness Classification:
- **`PRODUCTION_READY`**: **`{prod:,}` Hypotheses** (Strongly validated, replicated in 2025-2026, high stability)
- **`SHADOW_READY`**: **`{shadow:,}` Hypotheses** (Moderately/strongly validated, suitable for shadow execution)
- **`EXPERIMENTAL`**: **`{weak:,}` Hypotheses** (Weak statistical backing, requires more live data)
- **`RESEARCH_ONLY`**: **`{incon + refuted:,}` Hypotheses** (Inconclusive or refuted)

- **Preserved Rare Tail Events**: **`{len(self.rare_events_store):,}` extreme anomalies** (Crashes, Extreme Expansions, High Severity Stress) saved in `rare_events_knowledge.parquet`.

---

## 🔬 TOP STATISTICALLY VALIDATED & REPLICATED HYPOTHESES (SAMPLE OF TOP 25)

| Knowledge ID | Hypothesis Condition | Horizon | Sample (N) | Baseline (P_base %) | Observed (P_obs %) | Relative Risk (RR) | 95% Confidence Interval | Adj. p-value (FDR) | Replication Status | Stability (0-100) | Decision | Readiness |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- | :--- |
{table_str}

---

## 📦 VALIDATION ARTIFACTS GENERATED (`knowledge_base/v1/validation/`)

1. `v1/validation/knowledge_baselines.parquet` — Baseline rates (P_base %) per symbol, situation & horizon.
2. `v1/validation/knowledge_effect_sizes.parquet` — Relative Risk ($RR$) and Odds Ratios ($OR$).
3. `v1/validation/knowledge_confidence_intervals.parquet` — 95% Wilson binomial confidence intervals [CI_lower %, CI_upper %].
4. `v1/validation/knowledge_statistical_tests.parquet` — Chi-Square ($\chi^2$), raw $p$, FDR adjusted $p$, replication & stability.
5. `v1/validation/knowledge_validated_repository.parquet` — Master repository of all `{len(val_repo):,}` validated hypotheses.
6. `v1/rare_events_knowledge.parquet` — Scale-corrected rare market event store (`{len(self.rare_events_store):,}` records).
7. `v1/validation/knowledge_validation_summary.json` — Machine-readable summary for future AI model generators.
"""

        md_report_path = os.path.join(REPORTS_DIR, "step_4_5_knowledge_validation_report.md")
        with open(md_report_path, "w", encoding="utf-8") as f:
            f.write(md_report)
        log.info("Step 4.5 & 4.6 Executive Research Report Saved: %s", md_report_path)

    def run_full_validation_pipeline(self):
        self.stream_and_accumulate_data()
        self.execute_statistical_validation()
        log.info("=" * 80)
        log.info("STEP 4.5 & 4.6 KNOWLEDGE VALIDATION & STABILITY ENGINE v2.0 — COMPLETE!")
        log.info("=" * 80)


if __name__ == "__main__":
    engine = KnowledgeValidationEngineV2()
    engine.run_full_validation_pipeline()
