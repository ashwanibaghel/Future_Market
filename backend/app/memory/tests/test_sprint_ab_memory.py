"""
Sprint AB — Unit Test Suite for Market Memory Formation Engine v1.
Verifies collision-proof Hash ID generation, state-driven episode segmentation,
multi-horizon outcome evaluation, decoupled retrieval, and structural similarity matching.
"""

import unittest
from app.memory.taxonomy import generate_memory_id, EpisodicMemory
from app.memory.segmenter import EpisodeSegmenter
from app.memory.outcome import OutcomeEngine
from app.memory.similarity import StructuralSimilarityEngine

class TestSprintABMemory(unittest.TestCase):

    def test_collision_proof_hash_id(self):
        mid1 = generate_memory_id("NSE", "INDEX", "NIFTY", "2024-06-18T09:15:00Z")
        mid2 = generate_memory_id("NSE", "INDEX", "NIFTY", "2024-06-18T09:15:00Z")
        mid3 = generate_memory_id("NSE", "INDEX", "BANKNIFTY", "2024-06-18T09:15:00Z")

        self.assertTrue(mid1.startswith("MEM_NSE_INDEX_NIFTY_20240618T091500_"))
        self.assertEqual(mid1, mid2)
        self.assertNotEqual(mid1, mid3)

    def test_state_driven_segmentation(self):
        segmenter = EpisodeSegmenter()
        snap1 = {"timestamp": "2024-06-18T09:15:00Z", "symbol": "NIFTY", "exchange": "NSE", "spot_price": 23500.0}
        snap2 = {"timestamp": "2024-06-18T09:16:00Z", "symbol": "NIFTY", "exchange": "NSE", "spot_price": 23505.0}

        sits1 = [{"situation_id": "SIT_ACCUMULATION_BEHAVIOUR", "confidence": 0.85}]
        sits2 = []  # Dissolves situation

        comp1 = segmenter.process_snapshot_situations(snap1, sits1)
        self.assertEqual(len(comp1), 0)  # Active episode ongoing

        comp2 = segmenter.process_snapshot_situations(snap2, sits2)
        self.assertEqual(len(comp2), 1)  # Episode completed
        self.assertEqual(comp2[0]["situation_id"], "SIT_ACCUMULATION_BEHAVIOUR")

    def test_multi_horizon_outcome_calculation(self):
        outcome_engine = OutcomeEngine()
        ep = {
            "situation_id": "SIT_ACCUMULATION_BEHAVIOUR",
            "snapshots": [{"spot_price": 23500.0}]
        }
        subsequent = [
            {"spot_price": 23510.0},
            {"spot_price": 23530.0},
            {"spot_price": 23550.0}
        ]
        outcomes = outcome_engine.calculate_multi_horizon_outcomes(ep, subsequent)
        self.assertIn("horizon_5m", outcomes)
        self.assertIn("horizon_30m", outcomes)
        self.assertGreater(outcomes["horizon_30m"]["mfe_pct"], 0.0)

    def test_structural_similarity_matching(self):
        sim_engine = StructuralSimilarityEngine()
        cand = {"trend": "UPWARD_DRIFT", "volatility": "STABLE", "structure": "ACCUMULATION", "severity_level": 3, "pcr_oi": 1.30}
        hist = {"trend": "UPWARD_DRIFT", "volatility": "STABLE", "structure": "ACCUMULATION", "severity_level": 3, "pcr_oi": 1.32}

        score = sim_engine.compute_similarity(cand, hist)
        self.assertGreaterEqual(score, 0.90)

if __name__ == "__main__":
    unittest.main()
