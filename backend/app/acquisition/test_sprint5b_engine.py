import os
import json
import unittest
from unittest.mock import MagicMock

from app.acquisition.normalizer import DataNormalizer, CanonicalOptionCandle
from app.acquisition.engine import HistoricalBackfillEngine, PROGRESS_FILE, COVERAGE_REPORT_FILE
from app.research_os.governance.dataset_registry import ensure_research_storage_structure


class TestSprint5BEngine(unittest.TestCase):
    """Unit test suite for Sprint 5B: Decoupled Resumable Historical Backfill Engine."""

    def setUp(self):
        ensure_research_storage_structure()
        self.mock_client = MagicMock()
        self.engine = HistoricalBackfillEngine(client=self.mock_client)

    def test_01_data_normalizer(self):
        raw = {
            "timestamp": "2024-05-15T09:15:00",
            "open": 100.0,
            "high": 110.0,
            "low": 95.0,
            "close": 105.0,
            "volume": 1000,
            "open_interest": 50000,
            "implied_volatility": 14.2,
            "spot_price": 22500.0,
        }
        canonical = DataNormalizer.normalize_dhan_record(raw, "NIFTY", "ATM", "CALL", 1715764500)
        self.assertIsInstance(canonical, CanonicalOptionCandle)
        self.assertEqual(canonical.symbol, "NIFTY")
        self.assertEqual(canonical.provider, "DHAN")
        self.assertEqual(canonical.open_interest, 50000)

    def test_02_progress_checkpointing(self):
        self.engine.progress["completed"] = 100
        self.engine._save_progress()

        self.assertTrue(os.path.exists(PROGRESS_FILE))
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["completed"], 100)

    def test_03_coverage_report_generation(self):
        report = self.engine._generate_coverage_report(["NIFTY"], [2021, 2022])
        self.assertIn("2021", report["years"])
        self.assertTrue(os.path.exists(COVERAGE_REPORT_FILE))


if __name__ == "__main__":
    unittest.main()
