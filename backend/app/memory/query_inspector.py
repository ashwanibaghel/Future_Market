"""
Sprint AC — Memory Retrieval & Ranking Inspector CLI Tool
Terminal inspector tool allowing quantitative researchers to query any candidate situation,
retrieve top-10 historical memory matches with explainable similarity breakdowns, why_retrieved rationales,
diversity enforcement, and aggregated historical outcomes across 5.5 years of market history.
"""

import sys
import os
import json
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.memory.ranker import MemoryRankerEngine

def inspect_retrieval(
    situation_id: str = "SIT_LEVEL_BREACH_EXPANSION",
    policy: str = "DEFAULT",
    limit: int = 5
):
    print("=" * 80)
    print(f"  MEMORY RETRIEVAL & RANKING ENGINE v1 -- INSPECTOR ({situation_id})")
    print(f"  Applied Weight Policy: {policy}")
    print("=" * 80)

    ranker = MemoryRankerEngine()

    candidate_situation = {
        "symbol": "NIFTY",
        "situation_id": situation_id,
        "features": {
            "trend": "DOWNWARD_PRESSURE",
            "volatility": "EXPANDING",
            "participation": "HIGH_INSTITUTIONAL",
            "structure": "EXPANSION_BREAKOUT",
            "pcr_oi": 1.0,
            "severity_level": 4
        }
    }

    results = ranker.retrieve_and_rank(
        candidate_situation=candidate_situation,
        policy_name=policy,
        top_k=limit,
        max_per_month=3
    )

    print(f"Stage 1 Fast Filtered Candidates : {results['total_stage1_candidates']}")
    print(f"Stage 2 Scored Matches (>=50%)   : {results['total_matching_memories']}")
    print(f"Top-{limit} Diverse Ranked Episodes Retrieved:")
    print("-" * 80)

    top_mems = results["top_ranked_memories"]
    for idx, m in enumerate(top_mems, start=1):
        print(f"\n[{idx}] Memory ID: {m['memory_id']} (Sim Score: {m['similarity_percent']})")
        print(f"    |-- Start Time    : {m['start_time']} (Duration: {m['duration_minutes']}m)")
        print(f"    |-- Match Breakdown: Trend={m['breakdown']['trend_match']} | Vol={m['breakdown']['volatility_match']} | Struct={m['breakdown']['structure_match']} | PCR={m['breakdown']['pcr_proximity']}")
        print(f"    |-- Why Retrieved  : {', '.join(m['why_retrieved'])}")
        h30 = m['episode_outcomes'].get('horizon_30m', {})
        print(f"    |-- 30m Outcome   : Direction={h30.get('direction')} (MFE: +{h30.get('mfe_pct')}%, MAE: {h30.get('mae_pct')}%)")

    print("\n" + "=" * 80)
    print("  AGGREGATED HISTORICAL OUTCOMES (Top-K Sample):")
    outs = results["aggregated_historical_outcomes"]
    print(f"  |-- Sample Size        : {outs.get('top_k_sample_size')} episodes")
    print(f"  |-- Resolution Dist.   : {outs.get('horizon_30m_resolution_distribution')}")
    print(f"  |-- Average 30m MFE    : {outs.get('average_30m_mfe_pct')}")
    print(f"  |-- Average 30m MAE    : {outs.get('average_30m_mae_pct')}")
    print("=" * 80)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sprint AC Memory Retrieval Inspector")
    parser.add_argument("--sit", type=str, default="SIT_LEVEL_BREACH_EXPANSION", help="Situation ID to query")
    parser.add_argument("--policy", type=str, default="DEFAULT", help="Weight policy (DEFAULT, TRENDING_DAY, EXPIRY_DAY)")
    parser.add_argument("--limit", type=int, default=5, help="Top-K limit")

    args = parser.parse_args()
    inspect_retrieval(situation_id=args.sit, policy=args.policy, limit=args.limit)
