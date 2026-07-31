"""
Sprint AE — Competing Hypotheses Manager
Generates and maintains competing structural explanations (H_A vs H_B).
Enforces Cognitive Pipeline Contract: NEVER discards minority evidence.
"""

from typing import Dict, Any, List
from app.reasoning.taxonomy import HypothesisObject

class HypothesisManager:
    """
    Manages competing structural hypotheses (H_A vs H_B).
    Preserves minority evidence and contradiction rationales.
    """

    def build_competing_hypotheses(
        self,
        synthesis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Builds H_A (Primary Structural View) and H_B (Contradiction / Failure Mode View).
        """
        sit_id = synthesis.get("primary_situation", "")
        ev = synthesis.get("empirical_evidence", {})
        ca = synthesis.get("contradiction_summary", {})

        n = ev.get("sample_size", 0)
        sup = ev.get("supporting_memories", 0)
        contra = ev.get("contradicting_memories", 0)
        raw_rate = ev.get("raw_success_rate_pct", 0.0)

        # ── HYPOTHESIS A: PRIMARY STRUCTURAL VIEW ───────────────────────────
        is_high_support = raw_rate >= 55.0
        h_a_title = "Primary Trend / Structure Continuation" if is_high_support else "Alternative Structure Bias"
        h_a_rationale = (
            f"Supported by {sup}/{n} historical episodes ({raw_rate}% raw support rate). "
            f"Average favorable excursion of +{ev.get('average_favourable_excursion_pct', 0.0)}%."
        )

        h_a = HypothesisObject(
            title=h_a_title,
            supporting_evidence_count=sup,
            raw_support_pct=raw_rate,
            derived_confidence=round(min(0.95, raw_rate / 100.0), 2),
            rationale=h_a_rationale
        ).to_dict()

        # ── HYPOTHESIS B: CONTRADICTION / FAILURE MODE VIEW ─────────────────
        h_b_title = f"Failure Cluster: {ca.get('largest_failure_cluster', 'COUNTER_REVERSAL')}"
        h_b_rationale = (
            f"Preserved from {contra}/{n} contradicting historical episodes. "
            f"Primary breakdown trigger: {ca.get('common_trigger', 'Liquidity displacement')}."
        )
        h_b_support_pct = round(100.0 - raw_rate, 1)

        h_b = HypothesisObject(
            title=h_b_title,
            supporting_evidence_count=contra,
            raw_support_pct=h_b_support_pct,
            derived_confidence=round(min(0.95, h_b_support_pct / 100.0), 2),
            rationale=h_b_rationale
        ).to_dict()

        # ── MINORITY EVIDENCE PRESERVATION RATIONALE ────────────────────────
        minority_evidence = []
        if contra > 0:
            minority_evidence.append(
                f"Preserved {contra}/{n} failure episodes ({ca.get('largest_failure_cluster', 'COUNTER_REVERSAL')}): "
                f"{ca.get('common_trigger', 'Order book thinning triggered counter-reversal')}."
            )

        return {
            "hypothesis_A": h_a,
            "hypothesis_B": h_b,
            "minority_evidence_preserved": minority_evidence
        }
