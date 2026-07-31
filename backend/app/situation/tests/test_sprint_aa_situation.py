"""
Sprint AA — Market Situation Understanding Engine v1 Unit Tests.
Verifies descriptive situation taxonomy, 4-pillar market context, multi-factor confidence,
temporal evolution phases, and mandatory explainable 'why' cards.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from app.situation.taxonomy import (
    EvolutionPhase,
    StructurePillar,
    SITUATION_TAXONOMY
)
from app.situation.engine import SituationEngine

class TestSprintAASituationEngine(unittest.TestCase):

    def setUp(self):
        self.engine = SituationEngine()

    def test_descriptive_taxonomy_mapping(self):
        """Verifies that all situations in taxonomy use descriptive market-behavior names."""
        self.assertGreaterEqual(len(SITUATION_TAXONOMY), 6, "Taxonomy registry incomplete!")
        for sit_id, data in SITUATION_TAXONOMY.items():
            self.assertTrue(sit_id.startswith("SIT_"), f"Invalid ID format: {sit_id}")
            self.assertIn("description", data)
            self.assertIn("default_structure", data)

    def test_accumulation_behaviour_understanding(self):
        """Verifies situation understanding, 4-pillar context, multi-factor confidence, and explainable why cards."""
        snapshot = {
            "snapshot_id": "NIFTY_1700000000_2024-06-27",
            "timestamp": "2024-06-18T09:30:00Z",
            "symbol": "NIFTY",
            "spot_price": 24000.0,
            "atm_strike": 24000.0
        }
        observations = [
            {
                "observation_id": "OBS_PUT_WRITING_AGGRESSIVE",
                "category": "OPEN_INTEREST",
                "severity_level": 3,
                "evidence": {"pcr_oi": 1.35, "put_oi_change_pct": 15.2}
            },
            {
                "observation_id": "OBS_ATM_UPSHIFT",
                "category": "ATM_SHIFT",
                "severity_level": 2,
                "evidence": {"prev_atm_strike": 23950.0, "new_atm_strike": 24000.0}
            },
            {
                "observation_id": "OBS_PCR_EXPANSION",
                "category": "VOLUME",
                "severity_level": 2,
                "evidence": {"pcr_oi": 1.35}
            }
        ]

        sits = self.engine.understand(snapshot, observations)
        self.assertEqual(len(sits), 1, "Failed to infer situation!")

        sit = sits[0]
        self.assertEqual(sit.situation_id, "SIT_ACCUMULATION_BEHAVIOUR")
        self.assertEqual(sit.evolution_phase, EvolutionPhase.BUILDING)
        self.assertGreaterEqual(sit.confidence, 0.70)
        self.assertIn("structure", sit.market_context)
        self.assertEqual(sit.market_context["structure"], StructurePillar.ACCULATION)
        self.assertTrue(len(sit.why) > 0, "Mandatory why array is empty!")
        self.assertIn("OBS_PUT_WRITING_AGGRESSIVE", sit.supporting_observations)

    def test_temporal_evolution_phase_progression(self):
        """Verifies temporal continuity tracking across consecutive timestamps (BUILDING -> SUSTAINED -> ACCELERATING)."""
        snapshot = {
            "snapshot_id": "NIFTY_1700000000_2024-06-27",
            "timestamp": "2024-06-18T09:30:00Z",
            "symbol": "NIFTY",
            "spot_price": 24000.0,
            "atm_strike": 24000.0
        }
        obs = [
            {"observation_id": "OBS_PUT_WRITING_AGGRESSIVE", "category": "OPEN_INTEREST", "severity_level": 3, "evidence": {"pcr_oi": 1.35}},
            {"observation_id": "OBS_ATM_UPSHIFT", "category": "ATM_SHIFT", "severity_level": 2, "evidence": {}}
        ]

        # Timestamp 1
        sits1 = self.engine.understand(snapshot, obs)
        self.assertEqual(sits1[0].evolution_phase, EvolutionPhase.BUILDING)
        self.assertEqual(sits1[0].duration_minutes, 1)

        # Timestamp 2
        snapshot["timestamp"] = "2024-06-18T09:31:00Z"
        sits2 = self.engine.understand(snapshot, obs)
        self.assertEqual(sits2[0].evolution_phase, EvolutionPhase.BUILDING)
        self.assertEqual(sits2[0].duration_minutes, 2)

        # Timestamp 3
        snapshot["timestamp"] = "2024-06-18T09:32:00Z"
        sits3 = self.engine.understand(snapshot, obs)
        self.assertEqual(sits3[0].evolution_phase, EvolutionPhase.SUSTAINED)
        self.assertEqual(sits3[0].duration_minutes, 3)

if __name__ == "__main__":
    unittest.main()
