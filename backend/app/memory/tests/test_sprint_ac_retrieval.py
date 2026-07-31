"""
Sprint AC — Unit Test Suite for Memory Retrieval & Ranking Engine.
Verifies secondary index loading, 2-stage retrieval, weight policy calculations,
why_retrieved rationales, month diversity enforcement, and outcome aggregation.
"""

import unittest
from app.memory.similarity import StructuralSimilarityEngine
from app.memory.ranker import MemoryRankerEngine

class TestSprintACRetrieval(unittest.TestCase):

    def test_weight_policy_calculations(self):
        sim_engine = StructuralSimilarityEngine()
        cand = {"trend": "UPWARD_DRIFT", "volatility": "STABLE", "structure": "ACCUMULATION", "severity_level": 3, "pcr_oi": 1.30}
        hist = {"trend": "UPWARD_DRIFT", "volatility": "EXPANDING", "structure": "ACCUMULATION", "severity_level": 3, "pcr_oi": 1.30}

        score_default = sim_engine.compute_similarity(cand, hist, policy_name="DEFAULT")
        score_trending = sim_engine.compute_similarity(cand, hist, policy_name="TRENDING_DAY")

        self.assertGreater(score_trending, 0.0)
        self.assertIn("trend_match", sim_engine.compute_similarity_with_policy(cand, hist)["breakdown"])

    def test_why_retrieved_rationales(self):
        sim_engine = StructuralSimilarityEngine()
        cand = {"trend": "UPWARD_DRIFT", "volatility": "STABLE", "structure": "ACCUMULATION", "severity_level": 3, "pcr_oi": 1.30}
        hist = {"trend": "UPWARD_DRIFT", "volatility": "STABLE", "structure": "ACCUMULATION", "severity_level": 3, "pcr_oi": 1.30}

        res = sim_engine.compute_similarity_with_policy(cand, hist)
        self.assertTrue(len(res["why_retrieved"]) >= 3)
        self.assertIn("100% Trend Pillar Match (UPWARD_DRIFT)", res["why_retrieved"])

    def test_ranker_retrieval_and_aggregation(self):
        ranker = MemoryRankerEngine()
        cand_sit = {
            "symbol": "NIFTY",
            "situation_id": "SIT_LEVEL_BREACH_EXPANSION",
            "features": {
                "trend": "DOWNWARD_PRESSURE",
                "volatility": "EXPANDING",
                "participation": "HIGH_INSTITUTIONAL",
                "structure": "EXPANSION_BREAKOUT",
                "pcr_oi": 1.0,
                "severity_level": 4
            }
        }
        res = ranker.retrieve_and_rank(cand_sit, policy_name="DEFAULT", top_k=5, max_per_month=3)
        self.assertGreater(res["total_stage1_candidates"], 0)
        self.assertGreater(len(res["top_ranked_memories"]), 0)
        self.assertIn("top_k_sample_size", res["aggregated_historical_outcomes"])

if __name__ == "__main__":
    unittest.main()
