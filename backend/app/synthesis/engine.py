"""
Sprint AD — Experience Synthesis Engine v1
Main Orchestrator synthesizing retrieved historical memories into evidence metrics,
contradiction failure clusters, and explainable Structural Hypotheses.

CRITICAL EVIDENCE CONSISTENCY GUARANTEE:
Hypothesis wording MUST be 100% consistent with empirical support rate.
If support rate < 55%, wording MUST explicitly state "less frequently associated / observed in only X% of episodes".
"""

from typing import List, Dict, Any, Optional

from app.synthesis.taxonomy import (
    generate_synthesis_id,
    ExperienceSynthesis,
    EmpiricalEvidence,
    ContradictionSummary,
    UnknownsAssessment
)
from app.synthesis.synthesizer import EvidenceSynthesizer
from app.synthesis.contradiction import ContradictionAnalyzer

class ExperienceSynthesisEngine:
    """
    Main Experience Synthesis Engine.
    Converts retrieved historical memories into audited ExperienceSynthesis objects.
    """

    def __init__(self):
        self.evidence_synthesizer = EvidenceSynthesizer()
        self.contradiction_analyzer = ContradictionAnalyzer()

    def synthesize_experience(
        self,
        current_situation: Dict[str, Any],
        retrieved_memories: List[Dict[str, Any]]
    ) -> ExperienceSynthesis:
        """
        Synthesizes historical memories into empirical evidence ratios, contradiction summaries,
        and an explainable, evidence-consistent Structural Hypothesis.
        """
        sit_id = current_situation.get("situation_id", "SIT_CONSOLIDATION_COMPRESSION")
        sym = current_situation.get("symbol", "NIFTY")
        exchange = current_situation.get("exchange", "NSE")
        snapshot_ts = current_situation.get("timestamp", "2026-07-01T03:45:00Z")

        # 1. Synthesize empirical evidence
        syn_res = self.evidence_synthesizer.synthesize_evidence(retrieved_memories, sit_id)
        evidence_data = syn_res["empirical_evidence"]
        contradicting_mems = syn_res["contradicting_list"]
        expected_dir = syn_res["expected_direction"]

        # 2. Contradiction Analysis
        contra_data = self.contradiction_analyzer.analyze_contradictions(contradicting_mems, expected_dir)

        # 3. Quantify Unknowns Assessment
        unknowns_list = current_situation.get("unknowns", [])
        u_cov = round((len(unknowns_list) / 5.0) * 100.0, 1)
        u_impact = "HIGH" if u_cov >= 40.0 else ("MEDIUM" if u_cov >= 20.0 else "LOW")

        unknowns_summary = UnknownsAssessment(
            unknowns_list=unknowns_list,
            unknown_coverage_pct=u_cov,
            unknown_impact=u_impact
        ).to_dict()

        # 4. Statistical Confidence & Warnings
        n = evidence_data["sample_size"]
        stat_warning = None
        if n < 15:
            stat_warning = f"[WARNING] Low Statistical Confidence (Sample Size = {n} < 15 minimum threshold)"

        raw_rate = evidence_data["raw_success_rate_pct"]
        certainty = "HIGH" if (raw_rate >= 75.0 and n >= 15) else ("MODERATE" if raw_rate >= 55.0 else "LOW")

        # 5. Formulate Strict Evidence-Consistent Structural Hypothesis
        if raw_rate >= 55.0:
            struct_hypothesis = (
                f"Historical evidence suggests that under comparable conditions, {sit_id} was MORE frequently associated "
                f"with {expected_dir} (Raw Support: {raw_rate}%, Weighted Support: {evidence_data['importance_weighted_success_rate_pct']}% across {n} episodes). "
                f"Primary breakdown trigger in failure cases: {contra_data.get('common_trigger', 'None')}."
            )
        else:
            struct_hypothesis = (
                f"Historical evidence indicates that under comparable conditions, {sit_id} was LESS frequently associated "
                f"with {expected_dir} ({expected_dir} occurred in only {raw_rate}% of episodes, {evidence_data['supporting_memories']}/{n}). "
                f"{evidence_data['contradicting_memories']}/{n} episodes resolved in alternative outcomes. "
                f"Largest failure cluster: {contra_data.get('largest_failure_cluster', 'UNKNOWN')} ({contra_data.get('common_trigger', 'None')})."
            )

        synth_id = generate_synthesis_id(exchange, "INDEX", sym, snapshot_ts)

        return ExperienceSynthesis(
            synthesis_id=synth_id,
            primary_situation=sit_id,
            symbol=sym,
            exchange=exchange,
            timestamp=snapshot_ts,
            empirical_evidence=evidence_data,
            contradiction_summary=contra_data,
            unknowns_assessment=unknowns_summary,
            structural_hypothesis=struct_hypothesis,
            certainty_level=certainty,
            statistical_warning=stat_warning
        )
