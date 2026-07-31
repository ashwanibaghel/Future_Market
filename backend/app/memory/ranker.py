"""
Sprint AC & AD — 2-Stage Memory Retrieval, Ranking & Outcome Aggregation Engine
Implements:
1. Stage 1 Fast Candidate Filtering (with Partition Memory Caching).
2. Stage 2 Deep Weighted Similarity Scoring with Explainable Match Rationales.
3. Month Diversity Enforcement (max 3 episodes per calendar month).
4. Top-10 Historical Outcome Aggregation (Resolution Win-Rate %, Avg MFE, Avg MAE, Statistical Confidence Warning).
"""

import os
import json
from typing import List, Dict, Any, Optional
from collections import Counter

import pyarrow.parquet as pq

from app.memory.similarity import StructuralSimilarityEngine

INDEX_FILE = "E:/Future Stock/research_storage/memory_store/memory_secondary_index.json"

class MemoryRankerEngine:
    """
    Cognitive Retrieval, Ranking & Aggregation Engine.
    """

    def __init__(self):
        self.similarity_engine = StructuralSimilarityEngine()
        self.secondary_index = self._load_index()
        self._partition_cache: Dict[str, List[Dict[str, Any]]] = {}

    def _load_index(self) -> Dict[str, Any]:
        if os.path.exists(INDEX_FILE):
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def retrieve_and_rank(
        self,
        candidate_situation: Dict[str, Any],
        policy_name: str = "DEFAULT",
        top_k: int = 10,
        max_per_month: int = 3
    ) -> Dict[str, Any]:
        """
        Executes 2-Stage Retrieval, Ranking, Diversity Filtering, and Outcome Aggregation.
        """
        sym = candidate_situation.get("symbol", "NIFTY")
        sit_id = candidate_situation.get("situation_id", "")
        cand_feats = candidate_situation.get("features", {})

        # ── STAGE 1: FAST CANDIDATE FILTERING ────────────────────────────────
        candidate_records = self._stage1_fast_filter(sym, sit_id)

        # ── STAGE 2: DEEP WEIGHTED SIMILARITY SCORING ────────────────────────
        scored_candidates = []
        for mem in candidate_records:
            hist_feats = mem.get("features", {})
            sim_res = self.similarity_engine.compute_similarity_with_policy(
                candidate_features=cand_feats,
                historical_features=hist_feats,
                policy_name=policy_name
            )

            if sim_res["similarity_score"] >= 0.50:
                scored_candidates.append({
                    "memory_id": mem.get("memory_id", ""),
                    "primary_situation": mem.get("primary_situation", ""),
                    "start_time": mem.get("start_time", ""),
                    "duration_minutes": mem.get("duration_minutes", 1),
                    "similarity_score": sim_res["similarity_score"],
                    "similarity_percent": sim_res["similarity_percent"],
                    "breakdown": sim_res["breakdown"],
                    "why_retrieved": sim_res["why_retrieved"],
                    "episode_outcomes": mem.get("episode_outcomes", {})
                })

        scored_candidates.sort(key=lambda x: x["similarity_score"], reverse=True)

        # ── DIVERSITY FILTER (Max 3 per Month) ──────────────────────────────
        month_counts = Counter()
        diverse_top_k = []

        for cand in scored_candidates:
            ym = cand["start_time"][:7] if len(cand["start_time"]) >= 7 else "UNKNOWN"
            if month_counts[ym] < max_per_month:
                month_counts[ym] += 1
                diverse_top_k.append(cand)
                if len(diverse_top_k) >= top_k:
                    break

        # ── HISTORICAL OUTCOME AGGREGATION ──────────────────────────────────
        aggregated_outcomes = self._aggregate_outcomes(diverse_top_k)

        return {
            "query_situation": sit_id,
            "policy_applied": policy_name,
            "total_stage1_candidates": len(candidate_records),
            "total_matching_memories": len(scored_candidates),
            "top_ranked_memories": diverse_top_k,
            "aggregated_historical_outcomes": aggregated_outcomes
        }

    def _stage1_fast_filter(self, symbol: str, sit_id: str) -> List[Dict[str, Any]]:
        by_sit = self.secondary_index.get("by_situation", {}).get(sit_id, [])
        if not by_sit:
            return []

        partitions = set()
        for item in by_sit:
            partitions.add(item["partition"])

        records = []
        for rel_part in partitions:
            abs_part = os.path.join("E:/Future Stock", rel_part)
            if not os.path.exists(abs_part):
                continue

            if abs_part in self._partition_cache:
                part_recs = self._partition_cache[abs_part]
            else:
                part_recs = []
                try:
                    tbl = pq.ParquetFile(abs_part).read()
                    dict_data = tbl.to_pydict()
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
                    self._partition_cache[abs_part] = part_recs
                except Exception:
                    continue

            records.extend(part_recs)

        return records

    def _aggregate_outcomes(self, memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not memories:
            return {"sample_size": 0, "statistical_warning": "⚠️ Zero Memory Candidates Found"}

        horizon_dirs = Counter()
        mfe_30m_list = []
        mae_30m_list = []

        for m in memories:
            outs = m.get("episode_outcomes", {})
            h30 = outs.get("horizon_30m", {})
            d = h30.get("direction", "SIDEWAYS_FLAT")
            horizon_dirs[d] += 1
            mfe_30m_list.append(float(h30.get("mfe_pct", 0.0)))
            mae_30m_list.append(float(h30.get("mae_pct", 0.0)))

        n = len(memories)
        avg_mfe = round(sum(mfe_30m_list) / n, 3) if n > 0 else 0.0
        avg_mae = round(sum(mae_30m_list) / n, 3) if n > 0 else 0.0

        dir_dist = {k: f"{v} / {n} ({round((v/n)*100, 1)}%)" for k, v in horizon_dirs.items()}

        stat_warning = None
        if n < 15:
            stat_warning = f"⚠️ Low Statistical Confidence (Sample Size = {n} < 15 minimum threshold)"

        res = {
            "top_k_sample_size": n,
            "horizon_30m_resolution_distribution": dir_dist,
            "average_30m_mfe_pct": f"+{avg_mfe}%",
            "average_30m_mae_pct": f"{avg_mae}%"
        }
        if stat_warning:
            res["statistical_warning"] = stat_warning

        return res
