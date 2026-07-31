"""
Sprint AF — Unit Test Suite for Decision Support Engine v1.
Verifies assessment ID generation, zero buy/sell signals, risk attribution,
information gap evaluation, execution readiness, 5-tier traceability, and immutable audit package.
"""

import unittest
from app.decision.taxonomy import generate_assessment_id
from app.decision.risk import RiskAttributionAnalyzer
from app.decision.gap import InformationGapEvaluator
from app.decision.readiness import ExecutionReadinessEvaluator
from app.decision.engine import DecisionSupportEngine

class TestSprintAFDecision(unittest.TestCase):

    def test_assessment_id_generation(self):
        aid = generate_assessment_id("NSE", "INDEX", "NIFTY", "2026-07-01T03:45:00Z")
        self.assertTrue(aid.startswith("DS_NSE_INDEX_NIFTY_20260701T034500_"))

    def test_risk_attribution_analyzer(self):
        analyzer = RiskAttributionAnalyzer()
        reasoning = {
            "primary_situation": "SIT_LEVEL_BREACH_EXPANSION",
            "competing_hypotheses": {
                "hypothesis_B": {"title": "Failure Cluster: ORDER_BOOK_VACUUM_REVERSAL", "supporting_evidence_count": 5, "rationale": "Order book thinning"}
            },
            "minority_evidence_preserved": ["5/10 failure episodes"]
        }
        res = analyzer.analyze_risks(reasoning)
        self.assertGreater(len(res["key_risks"]), 0)

    def test_information_gap_evaluator(self):
        evaluator = InformationGapEvaluator()
        reasoning = {"unknowns": ["IV unconfirmed"]}
        gap = evaluator.evaluate_information_gap(reasoning)
        self.assertIn("Live Order Book Delta", gap.missing_information)
        self.assertEqual(gap.gap_impact, "MEDIUM")

    def test_execution_readiness_evaluator(self):
        evaluator = ExecutionReadinessEvaluator()
        r1 = evaluator.evaluate_readiness(confidence_pct=80.0, contradiction_count=1, gap_impact="LOW")
        self.assertEqual(r1, "HIGH")
        r2 = evaluator.evaluate_readiness(confidence_pct=20.0, contradiction_count=5, gap_impact="MEDIUM")
        self.assertEqual(r2, "LOW")

    def test_decision_support_engine_zero_signals_and_audit(self):
        engine = DecisionSupportEngine()
        reasoning = {
            "reasoning_id": "REASON_TEST",
            "primary_situation": "SIT_ACCUMULATION_BEHAVIOUR",
            "symbol": "NIFTY",
            "exchange": "NSE",
            "timestamp": "2026-07-01T03:45:00Z",
            "competing_hypotheses": {
                "hypothesis_A": {"title": "Primary View", "supporting_evidence_count": 8, "rationale": "Strong support"},
                "hypothesis_B": {"title": "Failure View", "supporting_evidence_count": 2, "rationale": "Liquidity risk"}
            },
            "confidence_breakdown": {"final_derived_confidence": 0.68},
            "minority_evidence_preserved": ["2 failure episodes"],
            "unknowns": ["IV unconfirmed"]
        }
        ds = engine.generate_decision_support(reasoning)
        ds_dict = ds.to_dict()
        self.assertNotIn("action", ds_dict)
        self.assertNotIn("signal", ds_dict)
        self.assertIn("tier_5_assessment_id", ds_dict["traceability"])
        self.assertEqual(ds_dict["audit_package"]["software_version"], "v1.0-phase1-freeze")

if __name__ == "__main__":
    unittest.main()
