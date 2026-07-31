"""
Sprint AE — Explainable Derived Confidence Calculator
Calculates derived confidence scores mathematically using explicit formula:
Confidence = Evidence Strength * Sample Reliability * Data Completeness * (1.0 - Contradiction Penalty)
"""

from typing import Dict, Any
from app.reasoning.taxonomy import ConfidenceBreakdown

class ExplainableConfidenceCalculator:
    """
    Calculates 100% explainable derived confidence scores.
    """

    def calculate_derived_confidence(
        self,
        raw_support_pct: float,
        sample_size: int,
        unknown_coverage_pct: float,
        contradiction_count: int
    ) -> ConfidenceBreakdown:
        """
        Calculates mathematical derived confidence breakdown.
        """
        # 1. Evidence Strength (0.0 to 1.0)
        evidence_strength = min(1.0, max(0.0, raw_support_pct / 100.0))

        # 2. Sample Reliability (0.0 to 1.0 based on N vs threshold 15)
        sample_reliability = min(1.0, max(0.4, sample_size / 15.0))

        # 3. Data Completeness (0.0 to 1.0 based on unknown coverage)
        data_completeness = max(0.5, 1.0 - (unknown_coverage_pct / 100.0))

        # 4. Contradiction Penalty (0.0 to 0.4 based on failure ratio)
        fail_ratio = contradiction_count / max(1, sample_size)
        contradiction_penalty = min(0.4, max(0.0, fail_ratio * 0.5))

        # 5. Final Derived Confidence
        raw_conf = evidence_strength * sample_reliability * data_completeness * (1.0 - contradiction_penalty)
        final_conf = round(max(0.10, min(0.99, raw_conf)), 4)

        return ConfidenceBreakdown(
            evidence_strength=round(evidence_strength, 4),
            sample_reliability=round(sample_reliability, 4),
            data_completeness=round(data_completeness, 4),
            contradiction_penalty=round(contradiction_penalty, 4),
            final_derived_confidence=final_conf
        )
