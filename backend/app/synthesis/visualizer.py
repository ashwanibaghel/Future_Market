"""
Sprint AD — Experience Synthesis Engine v1
Experience Synthesis Inspector / Console Visualizer.

Terminal visualizer tool allowing quantitative research engineers to query any situation,
retrieve top historical memories, synthesize evidence, isolate failure clusters, and inspect
the resulting Structural Hypothesis.
"""

import sys
import os
import json
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.memory.ranker import MemoryRankerEngine
from app.synthesis.engine import ExperienceSynthesisEngine

def inspect_synthesis(
    situation_id: str = "SIT_LEVEL_BREACH_EXPANSION",
    policy: str = "DEFAULT",
    limit: int = 10
):
    print("=" * 80)
    print(f"  EXPERIENCE SYNTHESIS ENGINE v1 -- INSPECTOR ({situation_id})")
    print(f"  Applied Policy: {policy} | Top-K Sample Limit: {limit}")
    print("=" * 80)

    ranker = MemoryRankerEngine()
    synthesizer = ExperienceSynthesisEngine()

    candidate_situation = {
        "symbol": "NIFTY",
        "exchange": "NSE",
        "timestamp": "2026-07-01T03:45:00Z",
        "situation_id": situation_id,
        "unknowns": ["Implied Volatility expansion unconfirmed"],
        "features": {
            "trend": "DOWNWARD_PRESSURE",
            "volatility": "EXPANDING",
            "participation": "HIGH_INSTITUTIONAL",
            "structure": "EXPANSION_BREAKOUT",
            "pcr_oi": 1.0,
            "severity_level": 4
        }
    }

    # Step 1: Retrieve Top-K Memories
    retrieved_res = ranker.retrieve_and_rank(
        candidate_situation=candidate_situation,
        policy_name=policy,
        top_k=limit,
        max_per_month=3
    )

    memories = retrieved_res.get("top_ranked_memories", [])

    # Step 2: Synthesize Experience
    synthesis = synthesizer.synthesize_experience(candidate_situation, memories)
    synth_dict = synthesis.to_dict()

    print(f"\n[SYNTHESIS OBJECT] ID: {synth_dict['synthesis_id']}")
    print(f"   |-- Primary Situation : {synth_dict['primary_situation']}")
    print(f"   |-- Certainty Level   : {synth_dict['certainty_level']}")
    if synth_dict.get('statistical_warning'):
        print(f"   |-- Warning           : {synth_dict['statistical_warning']}")

    print("\n   [EMPIRICAL EVIDENCE]")
    ev = synth_dict["empirical_evidence"]
    print(f"   |-- Sample Size       : {ev['sample_size']} historical episodes")
    print(f"   |-- Supporting        : {ev['supporting_memories']} episodes")
    print(f"   |-- Contradicting     : {ev['contradicting_memories']} episodes")
    print(f"   |-- Raw Success Rate  : {ev['raw_success_rate_pct']}%")
    print(f"   |-- Weighted Support  : {ev['importance_weighted_success_rate_pct']}%")
    print(f"   |-- Avg 30m MFE / MAE : +{ev['average_favourable_excursion_pct']}% / {ev['average_adverse_excursion_pct']}%")

    print("\n   [CONTRADICTION ANALYSIS]")
    ca = synth_dict["contradiction_summary"]
    print(f"   |-- Failure Cluster   : {ca['largest_failure_cluster']} ({ca['failure_frequency']})")
    print(f"   |-- Breakdown Trigger : {ca['common_trigger']}")

    print("\n   [UNKNOWNS ASSESSMENT]")
    ua = synth_dict["unknowns_assessment"]
    print(f"   |-- Unknown Coverage  : {ua['unknown_coverage_pct']}% (Impact: {ua['unknown_impact']})")
    print(f"   |-- Declared Unknowns : {', '.join(ua['unknowns_list']) if ua['unknowns_list'] else 'None'}")

    print("\n   [STRUCTURAL HYPOTHESIS]")
    print(f"   \"{synth_dict['structural_hypothesis']}\"")

    print("\n" + "=" * 80)
    print("  SYNTHESIS COMPLETE -- 100% EXPLAINABLE HISTORICAL HYPOTHESIS FORMULATION")
    print("=" * 80)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sprint AD Experience Synthesis Inspector")
    parser.add_argument("--sit", type=str, default="SIT_LEVEL_BREACH_EXPANSION", help="Situation ID to synthesize")
    parser.add_argument("--policy", type=str, default="DEFAULT", help="Weight policy")
    parser.add_argument("--limit", type=int, default=10, help="Sample limit")

    args = parser.parse_args()
    inspect_synthesis(situation_id=args.sit, policy=args.policy, limit=args.limit)
