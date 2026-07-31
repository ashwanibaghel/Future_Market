"""
Sprint AF — Information Gap Evaluator
Identifies missing empirical information sources and quantifies information gap impact.
"""

from typing import Dict, Any, List
from app.decision.taxonomy import InformationGap

class InformationGapEvaluator:
    """
    Evaluates missing information sources and gap impact.
    """

    def evaluate_information_gap(
        self,
        reasoning_chain: Dict[str, Any]
    ) -> InformationGap:
        """
        Returns InformationGap object.
        """
        declared_unknowns = reasoning_chain.get("unknowns", [])

        missing_info = list(declared_unknowns)
        if "Live Order Book Delta" not in missing_info:
            missing_info.append("Live Order Book Delta")

        n_missing = len(missing_info)
        gap_impact = "HIGH" if n_missing >= 3 else ("MEDIUM" if n_missing >= 2 else "LOW")

        return InformationGap(
            missing_information=missing_info,
            gap_impact=gap_impact
        )
