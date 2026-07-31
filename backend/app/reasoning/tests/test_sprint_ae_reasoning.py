"""
Sprint AE — Unit Test Suite for Cognitive Reasoning Engine v1.
Verifies reasoning ID generation, derived confidence formula, hypothesis manager competing outputs,
and minority evidence preservation.
"""

import unittest
from app.reasoning.taxonomy import generate_reasoning_id
from app.reasoning.confidence import ExplainableConfidenceCalculator
from app.reasoning.manager import HypothesisManager
from app.reasoning.engine import CognitiveReasoningEngine

class TestSprintAEReasoning(unittest.TestCase):

    def test_reasoning_id_generation(self):
        rid = generate_reasoning_id("NSE", "INDEX", "NIFTY", "2026-07-01T03:45:00Z")
        self.assertTrue(rid.startswith("REASON_NSE_INDEX_NIFTY_20260701T034500_"))

    def test_explainable_confidence_formula(self):
        calc = ExplainableConfidenceCalculator()
        cb = calc.calculate_derived_confidence(raw_support_pct=80.0, sample_size=15, unknown_coverage_pct=10.0, contradiction_count=3)
        self.assertGreater(cb.final_derived_confidence, 0.40)
        self.assertEqual(cb.evidence_strength, 0.80)

    def test_competing_hypotheses_preservation(self):
        manager = HypothesisManager()
        synth = {
            "primary_situation": "SIT_LEVEL_BREACH_EXPANSION",
            "empirical_evidence": {"sample_size": 10, "supporting_memories": 8, "contradicting_memories": 2, "raw_success_rate_pct": 80.0},
            "contradiction_summary": {"largest_failure_cluster": "ORDER_BOOK_VACUUM_REVERSAL", "common_trigger": "Liquidity displacement", "contradicting_memories_count": 2}
        }
        res = manager.build_competing_hypotheses(synth)
        self.assertIn("hypothesis_A", res)
        self.assertIn("hypothesis_B", res)
        self.assertEqual(len(res["minority_evidence_preserved"]), 1)

    def test_cognitive_reasoning_engine(self):
        engine = CognitiveReasoningEngine()
        synth = {
            "primary_situation": "SIT_ACCUMULATION_BEHAVIOUR",
            "symbol": "NIFTY",
            "exchange": "NSE",
            "timestamp": "2026-07-01T03:45:00Z",
            "empirical_evidence": {"sample_size": 10, "supporting_memories": 8, "contradicting_memories": 2, "raw_success_rate_pct": 80.0},
            "contradiction_summary": {"largest_failure_cluster": "ORDER_BOOK_VACUUM_REVERSAL", "common_trigger": "Liquidity displacement", "contradicting_memories_count": 2},
            "unknowns_assessment": {"unknowns_list": ["IV unconfirmed"], "unknown_coverage_pct": 20.0, "unknown_impact": "MEDIUM"}
        }
        chain = engine.generate_reasoning_chain(synth)
        self.assertIn("Current empirical evidence favors", chain.overall_assessment)

if __name__ == "__main__":
    unittest.main()
