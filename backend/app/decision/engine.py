"""
Sprint AF — Decision Support Engine v1
Main Orchestrator converting Reasoning Chains into audited DecisionSupportAssessment objects.

📜 THE CONSTITUTION LINE (ARTICLE I & VIII):
"Zero buy/sell action signals. AI explains & assesses execution readiness; human decides."
"""

from typing import List, Dict, Any, Optional

from app.decision.taxonomy import (
    generate_assessment_id,
    DecisionSupportAssessment,
    InformationGap
)
from app.decision.risk import RiskAttributionAnalyzer
from app.decision.gap import InformationGapEvaluator
from app.decision.readiness import ExecutionReadinessEvaluator

class DecisionSupportEngine:
    """
    Main Decision Support Engine.
    Converts ReasoningChain objects into audited DecisionSupportAssessment objects.
    """

    def __init__(self):
        self.risk_analyzer = RiskAttributionAnalyzer()
        self.gap_evaluator = InformationGapEvaluator()
        self.readiness_evaluator = ExecutionReadinessEvaluator()

    def generate_decision_support(
        self,
        reasoning_chain_dict: Dict[str, Any],
        synthesis_dict: Optional[Dict[str, Any]] = None
    ) -> DecisionSupportAssessment:
        """
        Generates decision support assessment with risks, information gaps, execution readiness,
        5-tier traceability, and immutable audit package.
        """
        sit_id = reasoning_chain_dict.get("primary_situation", "SIT_CONSOLIDATION_COMPRESSION")
        sym = reasoning_chain_dict.get("symbol", "NIFTY")
        exchange = reasoning_chain_dict.get("exchange", "NSE")
        snapshot_ts = reasoning_chain_dict.get("timestamp", "2026-07-01T03:45:00Z")
        rid = reasoning_chain_dict.get("reasoning_id", "")

        hyps = reasoning_chain_dict.get("competing_hypotheses", {})
        h_a = hyps.get("hypothesis_A", {})
        h_b = hyps.get("hypothesis_B", {})

        dominant_hyp = h_a.get("title", "Primary Trend Continuation")

        cb = reasoning_chain_dict.get("confidence_breakdown", {})
        ev_conf_pct = round(cb.get("final_derived_confidence", 0.20) * 100.0, 1)

        # 1. Risk Attribution Analysis
        risk_res = self.risk_analyzer.analyze_risks(reasoning_chain_dict)
        key_risks = risk_res["key_risks"]
        rec_monitoring = risk_res["recommended_monitoring"]

        # 2. Key Supporting Evidence List
        key_supporting = [
            f"Hypothesis A: {h_a.get('title', 'Primary View')} ({h_a.get('supporting_evidence_count', 0)} supporting episodes).",
            f"Rationale: {h_a.get('rationale', '')}"
        ]

        # 3. Information Gap Evaluation
        info_gap = self.gap_evaluator.evaluate_information_gap(reasoning_chain_dict)
        info_gap_dict = info_gap.to_dict()

        # 4. Execution Readiness Evaluation
        contra_count = h_b.get("supporting_evidence_count", 0)
        readiness = self.readiness_evaluator.evaluate_readiness(
            confidence_pct=ev_conf_pct,
            contradiction_count=contra_count,
            gap_impact=info_gap_dict["gap_impact"]
        )

        # 5. 5-Tier Traceability Metadata
        synth_id = synthesis_dict.get("synthesis_id", "SYNTHESIS_PARENT_REF") if synthesis_dict else "SYNTHESIS_PARENT_REF"
        assessment_id = generate_assessment_id(exchange, "INDEX", sym, snapshot_ts)

        traceability = {
            "tier_5_assessment_id": assessment_id,
            "tier_4_reasoning_id": rid,
            "tier_3_synthesis_id": synth_id,
            "tier_2_primary_situation": sit_id,
            "tier_1_symbol": sym,
            "tier_0_timestamp": snapshot_ts
        }

        # 6. Immutable Audit Package (Scientific Reproducibility)
        audit_package = {
            "decision_id": assessment_id,
            "reasoning_id": rid,
            "synthesis_id": synth_id,
            "situation_id": sit_id,
            "snapshot_timestamp": snapshot_ts,
            "software_version": "v1.0-phase1-freeze",
            "constitution_version": "v1.0",
            "pipeline_version": "v1.0",
            "slogan": "Explain every assessment with evidence, uncertainty, and traceability."
        }

        return DecisionSupportAssessment(
            assessment_id=assessment_id,
            primary_situation=sit_id,
            symbol=sym,
            exchange=exchange,
            timestamp=snapshot_ts,
            dominant_hypothesis=dominant_hyp,
            evidence_quality_confidence=ev_conf_pct,
            key_supporting_evidence=key_supporting,
            key_risks=key_risks,
            information_gap=info_gap_dict,
            recommended_monitoring=rec_monitoring,
            execution_readiness=readiness,
            traceability=traceability,
            audit_package=audit_package
        )
