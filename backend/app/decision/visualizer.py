"""
Sprint AF — Decision Support Engine v1
Decision Support Inspector / Console Visualizer.

Terminal visualizer tool allowing quantitative research engineers to query any situation,
retrieve historical memories, synthesize experience, generate reasoning chains,
and inspect decision support assessments with 5-tier empirical traceability.
"""

import sys
import os
import json
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.memory.ranker import MemoryRankerEngine
from app.synthesis.engine import ExperienceSynthesisEngine
from app.reasoning.engine import CognitiveReasoningEngine
from app.decision.engine import DecisionSupportEngine

def inspect_decision_support(
    situation_id: str = "SIT_LEVEL_BREACH_EXPANSION",
    policy: str = "DEFAULT",
    limit: int = 10
):
    print("=" * 80)
    print(f"  DECISION SUPPORT ENGINE v1 -- INSPECTOR ({situation_id})")
    print(f"  Applied Policy: {policy} | Top-K Sample Limit: {limit}")
    print("=" * 80)

    ranker = MemoryRankerEngine()
    synthesizer = ExperienceSynthesisEngine()
    reasoning_engine = CognitiveReasoningEngine()
    decision_engine = DecisionSupportEngine()

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

    # Step 4: Generate Decision Support Assessment
    decision_assessment = decision_engine.generate_decision_support(chain_dict, synth_dict)
    ds_dict = decision_assessment.to_dict()

    print(f"\n[DECISION SUPPORT ASSESSMENT] ID: {ds_dict['assessment_id']}")
    print(f"   |-- Primary Situation   : {ds_dict['primary_situation']}")
    print(f"   |-- Dominant Hypothesis : {ds_dict['dominant_hypothesis']}")
    print(f"   |-- Evidence Conf. Quality: {ds_dict['evidence_quality_confidence']}%")
    print(f"   |-- Execution Readiness : [ {ds_dict['execution_readiness']} ]")

    print("\n   [KEY SUPPORTING EVIDENCE]")
    for item in ds_dict["key_supporting_evidence"]:
        print(f"   |-- {item}")

    print("\n   [KEY RISKS & CONTRADICTIONS]")
    for item in ds_dict["key_risks"]:
        print(f"   |-- {item}")

    print("\n   [INFORMATION GAP ASSESSMENT]")
    ig = ds_dict["information_gap"]
    print(f"   |-- Gap Impact Impact  : {ig['gap_impact']}")
    print(f"   |-- Missing Data Sources: {', '.join(ig['missing_information'])}")

    print("\n   [RECOMMENDED MONITORING PARAMETERS]")
    for item in ds_dict["recommended_monitoring"]:
        print(f"   |-- {item}")

    print("\n   [5-TIER EMPIRICAL TRACEABILITY]")
    tr = ds_dict["traceability"]
    print(f"   |-- Tier 5 (Decision ID) : {tr['tier_5_assessment_id']}")
    print(f"   |-- Tier 4 (Reasoning ID): {tr['tier_4_reasoning_id']}")
    print(f"   |-- Tier 3 (Synthesis ID): {tr['tier_3_synthesis_id']}")
    print(f"   |-- Tier 2 (Situation)   : {tr['tier_2_primary_situation']}")
    print(f"   |-- Tier 0 (Snapshot TS) : {tr['tier_0_timestamp']}")

    print("\n" + "=" * 80)
    print("  DECISION SUPPORT COMPLETE -- ZERO BUY/SELL SIGNALS, 100% EXPLAINABLE HUMAN OVERSIGHT")
    print("=" * 80)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sprint AF Decision Support Engine Inspector")
    parser.add_argument("--sit", type=str, default="SIT_LEVEL_BREACH_EXPANSION", help="Situation ID to evaluate")
    parser.add_argument("--policy", type=str, default="DEFAULT", help="Weight policy")
    parser.add_argument("--limit", type=int, default=10, help="Sample limit")

    args = parser.parse_args()
    inspect_decision_support(situation_id=args.sit, policy=args.policy, limit=args.limit)
