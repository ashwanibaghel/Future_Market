"""
Sprint AD — Evidence Synthesizer
Calculates raw and importance-weighted success rates across retrieved historical memories.
"""

from typing import List, Dict, Any
from collections import Counter
from app.synthesis.taxonomy import EmpiricalEvidence
from app.synthesis.importance import MemoryImportanceEvaluator

class EvidenceSynthesizer:
    """
    Synthesizes empirical evidence and weighted outcome distributions from historical memories.
    """

    def __init__(self):
        self.importance_evaluator = MemoryImportanceEvaluator()

    def synthesize_evidence(
        self,
        retrieved_memories: List[Dict[str, Any]],
        primary_situation: str
    ) -> Dict[str, Any]:
        """
        Calculates raw success rate, importance-weighted success rate, and excursion averages.
        """
        n = len(retrieved_memories)

        if n == 0:
            evidence = EmpiricalEvidence(
                sample_size=0,
                supporting_memories=0,
                contradicting_memories=0,
                raw_success_rate_pct=0.0,
                importance_weighted_success_rate_pct=0.0,
                average_favourable_excursion_pct=0.0,
                average_adverse_excursion_pct=0.0
            ).to_dict()

            return {
                "empirical_evidence": evidence,
                "supporting_list": [],
                "contradicting_list": [],
                "expected_direction": "SIDEWAYS_DRIFT"
            }

        # Determine dominant expected direction
        direction_counts = Counter()
        for m in retrieved_memories:
            outs = m.get("episode_outcomes", {})
            h30 = outs.get("horizon_30m", {})
            d = h30.get("direction", "SIDEWAYS_FLAT")
            direction_counts[d] += 1

        expected_direction = direction_counts.most_common(1)[0][0] if direction_counts else "UPWARD_EXPANSION"

        supporting = []
        contradicting = []
        mfe_list = []
        mae_list = []

        total_weight = 0.0
        supporting_weight = 0.0

        for m in retrieved_memories:
            w = self.importance_evaluator.calculate_importance_weight(m)
            total_weight += w

            outs = m.get("episode_outcomes", {})
            h30 = outs.get("horizon_30m", {})
            d = h30.get("direction", "SIDEWAYS_FLAT")

            mfe = float(h30.get("mfe_pct", 0.0))
            mae = float(h30.get("mae_pct", 0.0))
            mfe_list.append(mfe)
            mae_list.append(mae)

            if d == expected_direction:
                supporting.append(m)
                supporting_weight += w
            else:
                contradicting.append(m)

        sup_cnt = len(supporting)
        contra_cnt = len(contradicting)

        raw_rate = round((sup_cnt / n) * 100.0, 1) if n > 0 else 0.0
        weighted_rate = round((supporting_weight / max(0.001, total_weight)) * 100.0, 1)

        avg_mfe = round(sum(mfe_list) / max(1, n), 3)
        avg_mae = round(sum(mae_list) / max(1, n), 3)

        evidence = EmpiricalEvidence(
            sample_size=n,
            supporting_memories=sup_cnt,
            contradicting_memories=contra_cnt,
            raw_success_rate_pct=raw_rate,
            importance_weighted_success_rate_pct=weighted_rate,
            average_favourable_excursion_pct=avg_mfe,
            average_adverse_excursion_pct=avg_mae
        ).to_dict()

        return {
            "empirical_evidence": evidence,
            "supporting_list": supporting,
            "contradicting_list": contradicting,
            "expected_direction": expected_direction
        }
