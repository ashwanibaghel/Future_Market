"""
Sprint AF — Risk Attribution Analyzer
Extracts key risks, failure mode triggers, and recommended monitoring items
from reasoning chains and competing hypotheses.
"""

from typing import Dict, Any, List

class RiskAttributionAnalyzer:
    """
    Isolates structural risks, failure triggers, and monitoring parameters.
    """

    def analyze_risks(
        self,
        reasoning_chain: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Returns key risks and recommended monitoring parameters.
        """
        hyps = reasoning_chain.get("competing_hypotheses", {})
        h_b = hyps.get("hypothesis_B", {})
        sit_id = reasoning_chain.get("primary_situation", "")

        key_risks = []
        if h_b.get("rationale"):
            key_risks.append(f"Failure Risk: {h_b.get('title')} ({h_b.get('supporting_evidence_count')} historical failure episodes).")

        me = reasoning_chain.get("minority_evidence_preserved", [])
        for item in me:
            key_risks.append(f"Preserved Minority Risk: {item}")

        recommended_monitoring = [
            f"Track continuous volume participation during {sit_id}.",
            "Monitor PCR threshold boundary for structural unwinding.",
            "Verify ATM strike shift alignment across subsequent 5m intervals."
        ]

        return {
            "key_risks": key_risks,
            "recommended_monitoring": recommended_monitoring
        }
