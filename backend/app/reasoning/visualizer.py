"""
Sprint AE — Cognitive Reasoning Engine v1
Reasoning Chain Inspector / Console Visualizer.

Terminal visualizer tool allowing quantitative research engineers to query any situation,
retrieve historical memories, synthesize experience, generate competing hypotheses,
and inspect derived confidence breakdowns.
"""

import sys
import os
import json
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.memory.ranker import MemoryRankerEngine
from app.synthesis.engine import ExperienceSynthesisEngine
from app.reasoning.engine import CognitiveReasoningEngine

def inspect_reasoning(
    situation_id: str = "SIT_LEVEL_BREACH_EXPANSION",
    policy: str = "DEFAULT",
    limit: int = 10
):
    print("=" * 80)
    print(f"  COGNITIVE REASONING ENGINE v1 -- INSPECTOR ({situation_id})")
    print(f"  Applied Policy: {policy} | Top-K Sample Limit: {limit}")
    print("=" * 80)

    ranker = MemoryRankerEngine()
    synthesizer = ExperienceSynthesisEngine()
    reasoning_engine = CognitiveReasoningEngine()

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

    # Step 3: Generate Reasoning Chain
    reasoning_chain = reasoning_engine.generate_reasoning_chain(synth_dict)
    chain_dict = reasoning_chain.to_dict()

    print(f"\n[REASONING CHAIN OBJECT] ID: {chain_dict['reasoning_id']}")
    print(f"   |-- Primary Situation : {chain_dict['primary_situation']}")
    print(f"   |-- Timestamp         : {chain_dict['timestamp']}")

    print("\n   [COMPETING HYPOTHESES]")
    hyps = chain_dict["competing_hypotheses"]
    h_a = hyps["hypothesis_A"]
    h_b = hyps["hypothesis_B"]

    print(f"   |-- HYPOTHESIS A: {h_a['title']}")
    print(f"   |     * Evidence Count : {h_a['supporting_evidence_count']} episodes (Support: {h_a['raw_support_pct']}%)")
    print(f"   |     * Rationale      : {h_a['rationale']}")
    print(f"   |-- HYPOTHESIS B: {h_b['title']}")
    print(f"   |     * Evidence Count : {h_b['supporting_evidence_count']} episodes (Support: {h_b['raw_support_pct']}%)")
    print(f"   |     * Rationale      : {h_b['rationale']}")

    print("\n   [DERIVED CONFIDENCE BREAKDOWN]")
    cb = chain_dict["confidence_breakdown"]
    print(f"   |-- Evidence Strength   : {cb['evidence_strength']}")
    print(f"   |-- Sample Reliability  : {cb['sample_reliability']}")
    print(f"   |-- Data Completeness   : {cb['data_completeness']}")
    print(f"   |-- Contradiction Pen.  : -{cb['contradiction_penalty']}")
    print(f"   |-- Final Derived Conf. : {cb['final_derived_confidence']*100:.1f}%")

    print("\n   [MINORITY EVIDENCE PRESERVED]")
    me = chain_dict["minority_evidence_preserved"]
    if me:
        for item in me:
            print(f"   |-- {item}")
    else:
        print("   |-- None")

    print("\n   [OVERALL STRUCTURAL ASSESSMENT]")
    print(f"   \"{chain_dict['overall_assessment']}\"")

    print("\n" + "=" * 80)
    print("  REASONING COMPLETE -- 100% EXPLAINABLE COMPETING STRUCTURAL HYPOTHESES")
    print("=" * 80)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sprint AE Reasoning Engine Inspector")
    parser.add_argument("--sit", type=str, default="SIT_LEVEL_BREACH_EXPANSION", help="Situation ID to reason")
    parser.add_argument("--policy", type=str, default="DEFAULT", help="Weight policy")
    parser.add_argument("--limit", type=int, default=10, help="Sample limit")

    args = parser.parse_args()
    inspect_reasoning(situation_id=args.sit, policy=args.policy, limit=args.limit)
