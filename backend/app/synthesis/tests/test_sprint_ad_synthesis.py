"""
Sprint AD — Unit Test Suite for Experience Synthesis Engine.
Verifies raw vs weighted success rate synthesis, contradiction failure cluster analysis,
unknowns impact assessment, and explainable hypothesis generation.
"""

import unittest
from app.synthesis.taxonomy import generate_synthesis_id, ExperienceSynthesis
from app.synthesis.importance import MemoryImportanceEvaluator
from app.synthesis.contradiction import ContradictionAnalyzer
from app.synthesis.synthesizer import EvidenceSynthesizer
from app.synthesis.engine import ExperienceSynthesisEngine

class TestSprintADSynthesis(unittest.TestCase):

    def test_synthesis_id_generation(self):
        sid = generate_synthesis_id("NSE", "INDEX", "NIFTY", "2026-07-01T03:45:00Z")
        self.assertTrue(sid.startswith("SYN_NSE_INDEX_NIFTY_20260701T034500_"))

    def test_memory_importance_evaluator(self):
        evaluator = MemoryImportanceEvaluator()
        mem = {
            "primary_situation": "SIT_LEVEL_BREACH_EXPANSION",
            "duration_minutes": 20,
            "features": {"severity_level": 4}
        }
        w = evaluator.calculate_importance_weight(mem)
        self.assertGreaterEqual(w, 1.5)

    def test_contradiction_analyzer(self):
        analyzer = ContradictionAnalyzer()
        contradicting = [
            {"features": {"participation": "THIN_FLOW", "pcr_oi": 0.90}},
            {"features": {"participation": "THIN_FLOW", "pcr_oi": 0.95}}
        ]
        res = analyzer.analyze_contradictions(contradicting, "UPWARD_EXPANSION")
        self.assertEqual(res["contradicting_memories_count"], 2)
        self.assertEqual(res["largest_failure_cluster"], "LOW_INSTITUTIONAL_VOLUME")

    def test_experience_synthesis_engine(self):
        engine = ExperienceSynthesisEngine()
        cand = {
            "symbol": "NIFTY",
            "exchange": "NSE",
            "timestamp": "2026-07-01T03:45:00Z",
            "situation_id": "SIT_ACCUMULATION_BEHAVIOUR",
            "unknowns": ["IV expansion unconfirmed"]
        }
        memories = [
            {
                "primary_situation": "SIT_ACCUMULATION_BEHAVIOUR",
                "duration_minutes": 10,
                "features": {"severity_level": 3},
                "episode_outcomes": {"horizon_30m": {"direction": "UPWARD_EXPANSION", "mfe_pct": 0.5, "mae_pct": -0.1}}
            }
        ]
        synth = engine.synthesize_experience(cand, memories)
        self.assertEqual(synth.empirical_evidence["supporting_memories"], 1)
        self.assertIn("Historical evidence suggests", synth.structural_hypothesis)

if __name__ == "__main__":
    unittest.main()
