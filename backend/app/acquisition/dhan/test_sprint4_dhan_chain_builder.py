import os
import unittest
from unittest.mock import MagicMock

from app.acquisition.dhan.downloader import RollingStrikeDownloader
from app.acquisition.dhan.chain_builder import HistoricalOptionChainBuilder
from app.research_os.governance.dataset_registry import DatasetRegistry, ensure_research_storage_structure


class TestSprint4DhanChainBuilder(unittest.TestCase):
    """Unit test suite for Sprint 4: Multi-Strike Historical Option Chain Matrix Builder."""

    def setUp(self):
        ensure_research_storage_structure()
        self.mock_downloader = MagicMock(spec=RollingStrikeDownloader)
        self.builder = HistoricalOptionChainBuilder(downloader=self.mock_downloader)

    def test_01_build_option_chain_dataset(self):
        # Mock single strike downloader response
        self.mock_downloader.fetch_multi_month_strike.return_value = [
            {
                "timestamp": "2024-05-15T09:15:00",
                "open": 150.0,
                "high": 160.0,
                "low": 145.0,
                "close": 155.0,
                "volume": 500,
                "open_interest": 25000,
                "implied_volatility": 14.5,
                "spot_price": 22450.0,
            }
        ]

        # Run multi-strike option chain builder for 2 relative strikes (ATM, ATM+1)
        res = self.builder.build_option_chain_dataset(
            symbol="NIFTY",
            start_date="2024-05-15",
            end_date="2024-05-15",
            relative_strikes=["ATM", "ATM+1"],
            dataset_version="DS-v1.0.0"
        )

        self.assertTrue(res["success"])
        # 2 strikes * 2 option types (CALL, PUT) * 1 candle = 4 exported records
        self.assertEqual(res["total_exported"], 4)
        self.assertEqual(res["total_api_calls"], 4)
        self.assertTrue(os.path.exists(res["written_files"][0]))
        self.assertTrue(os.path.exists(res["checksum_path"]))

        # Verify Dataset Registry record
        registry = DatasetRegistry()
        reg_entry = registry.get_dataset(res["dataset_id"])
        self.assertIsNotNone(reg_entry)
        self.assertEqual(reg_entry["status"], "VALIDATED")
        self.assertEqual(reg_entry["total_rows"], 4)


if __name__ == "__main__":
    unittest.main()
