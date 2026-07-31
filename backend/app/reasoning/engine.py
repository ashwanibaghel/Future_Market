"""
Sprint AE — Cognitive Reasoning Engine v1
Main Orchestrator converting Experience Syntheses into audited ReasoningChain objects.

📜 THE CONSTITUTION LINE (ARTICLE VI & VIII):
"Evidence -> Confidence (NEVER Confidence -> Evidence).
Decision -> Outcome -> Learning."
"""

from typing import List, Dict, Any, Optional

from app.reasoning.taxonomy import (
    generate_reasoning_id,
    ReasoningChain
)
from app.reasoning.manager import HypothesisManager
from app.reasoning.confidence import ExplainableConfidenceCalculator

class CognitiveReasoningEngine:
    """
    Main Cognitive Reasoning Engine.
    Converts ExperienceSyntheses into audited ReasoningChain objects.
    """

    def __init__(self):
        self.hypothesis_manager = HypothesisManager()
        self.confidence_calculator = ExplainableConfidenceCalculator()

    def generate_reasoning_chain(
        self,
        synthesis_dict: Dict[str, Any]
    ) -> ReasoningChain:
        """
        Generates competing hypotheses, calculates derived confidence breakdown,
        and formulates explainable Reasoning Chains.
        """
        sit_id = synthesis_dict.get("primary_situation", "SIT_CONSOLIDATION_COMPRESSION")
        sym = synthesis_dict.get("symbol", "NIFTY")
        exchange = synthesis_dict.get("exchange", "NSE")
        snapshot_ts = synthesis_dict.get("timestamp", "2026-07-01T03:45:00Z")

        ev = synthesis_dict.get("empirical_evidence", {})
        ua = synthesis_dict.get("unknowns_assessment", {})
        ca = synthesis_dict.get("contradiction_summary", {})

        n = ev.get("sample_size", 0)
        raw_rate = ev.get("raw_success_rate_pct", 0.0)
        u_cov = ua.get("unknown_coverage_pct", 0.0)
        contra_count = ca.get("contradicting_memories_count", 0)

        # 1. Build Competing Hypotheses & Preserve Minority Evidence
        comp_res = self.hypothesis_manager.build_competing_hypotheses(synthesis_dict)
        hypotheses = {
            "hypothesis_A": comp_res["hypothesis_A"],
            "hypothesis_B": comp_res["hypothesis_B"]
        }
        minority_evidence = comp_res["minority_evidence_preserved"]

        # 2. Calculate Derived Confidence Breakdown
        conf_breakdown = self.confidence_calculator.calculate_derived_confidence(
            raw_support_pct=raw_rate,
            sample_size=n,
            unknown_coverage_pct=u_cov,
            contradiction_count=contra_count
        ).to_dict()

        final_conf_pct = int(conf_breakdown["final_derived_confidence"] * 100)

        # 3. Formulate Overall Assessment
        h_a_title = hypotheses["hypothesis_A"]["title"]
        h_b_title = hypotheses["hypothesis_B"]["title"]

        assessment = (
            f"Current empirical evidence favors {h_a_title} ({final_conf_pct}% derived confidence across {n} episodes), "
            f"but {h_b_title} remains plausible if {ca.get('common_trigger', 'order book liquidity deteriorates')}."
        )

        reasoning_id = generate_reasoning_id(exchange, "INDEX", sym, snapshot_ts)

        return ReasoningChain(
            reasoning_id=reasoning_id,
            primary_situation=sit_id,
            symbol=sym,
            exchange=exchange,
            timestamp=snapshot_ts,
            competing_hypotheses=hypotheses,
            confidence_breakdown=conf_breakdown,
            minority_evidence_preserved=minority_evidence,
            unknowns=ua.get("unknowns_list", []),
            overall_assessment=assessment
        )
