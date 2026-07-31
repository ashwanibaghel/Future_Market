"""
Sprint Z — Phase 7: Artificial Market Perception Engine Unit Tests.
Verifies MECE taxonomy, explainable rule engine output, evidence dictionary completeness,
and Observation Store schema integrity.
"""

import os
import json
import unittest
from app.perception.taxonomy import (
    ObservationCategory,
    SeverityLevel,
    Observation,
    OBSERVATION_TAXONOMY
)
from app.perception.engine import ObservationEngine

class TestSprintZPerceptionEngine(unittest.TestCase):

    def setUp(self):
        self.engine = ObservationEngine()

    def test_taxonomy_mece_structure(self):
        """Verifies that all registered taxonomy items have valid categories and descriptions."""
        self.assertGreater(len(OBSERVATION_TAXONOMY), 10, "Taxonomy registry is incomplete!")
        for obs_id, data in OBSERVATION_TAXONOMY.items():
            self.assertTrue(obs_id.startswith("OBS_"), f"Invalid ID format: {obs_id}")
            self.assertIn("category", data)
            self.assertIn("description", data)

    def test_aggressive_put_writing_rule(self):
        """Verifies that Aggressive Put Writing generates structured observations with explicit evidence."""
        snapshot = {
            "snapshot_id": "NIFTY_1700000000_2024-06-27",
            "timestamp": "2024-06-18T09:30:00Z",
            "epoch_ts": 1700000000,
            "symbol": "NIFTY",
            "spot_price": 24000.0,
            "expiry": "2024-06-27",
            "atm_strike": 24000.0
        }
        features = {
            "pcr_volume": 1.45,
            "pcr_oi": 1.35,
            "tot_call_oi": 100000,
            "tot_put_oi": 135000,
            "call_wall_strike": 24200.0,
            "put_floor_strike": 23800.0
        }
        prev_snapshot = {
            "spot_price": 23980.0,
            "atm_strike": 24000.0
        }
        prev_features = {
            "pcr_oi": 1.20,
            "tot_call_oi": 100000,
            "tot_put_oi": 120000
        }

        observations = self.engine.observe(snapshot, [], features, prev_snapshot, prev_features)
        self.assertTrue(len(observations) > 0, "No observations generated!")

        put_writing_obs = [o for o in observations if o.observation_id == "OBS_PUT_WRITING_AGGRESSIVE"]
        self.assertEqual(len(put_writing_obs), 1, "Aggressive Put Writing rule failed to trigger!")

        obs = put_writing_obs[0]
        self.assertEqual(obs.category, ObservationCategory.OPEN_INTEREST)
        self.assertGreaterEqual(obs.confidence, 0.80)
        self.assertIn("pcr_oi", obs.evidence)
        self.assertIn("put_oi_change_pct", obs.evidence)
        self.assertEqual(obs.evidence["pcr_oi"], 1.35)

    def test_call_wall_breach_rule(self):
        """Verifies Call Wall Breach observation when spot trades above Call Wall."""
        snapshot = {
            "snapshot_id": "NIFTY_1700000100_2024-06-27",
            "timestamp": "2024-06-18T09:31:00Z",
            "epoch_ts": 1700000100,
            "symbol": "NIFTY",
            "spot_price": 24250.0,
            "expiry": "2024-06-27",
            "atm_strike": 24200.0
        }
        features = {
            "pcr_volume": 1.0,
            "pcr_oi": 1.0,
            "call_wall_strike": 24200.0,
            "put_floor_strike": 23800.0,
            "tot_call_oi": 100000,
            "tot_put_oi": 100000
        }

        observations = self.engine.observe(snapshot, [], features)
        breach_obs = [o for o in observations if o.observation_id == "OBS_CALL_WALL_BREACH"]
        self.assertEqual(len(breach_obs), 1, "Call Wall Breach rule failed to trigger!")
        obs = breach_obs[0]
        self.assertEqual(obs.evidence["spot_price"], 24250.0)
        self.assertEqual(obs.evidence["call_wall_strike"], 24200.0)
        self.assertEqual(obs.evidence["breach_amount"], 50.0)

if __name__ == "__main__":
    unittest.main()
