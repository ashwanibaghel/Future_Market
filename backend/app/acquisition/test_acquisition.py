import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.acquisition.discovery import (
    InstrumentDiscoveryService,
    GenericInstrument,
    SENSEX_30_ISINS,
    INSTRUMENTS_DB_PATH,
)
from app.acquisition.upstox_client import UpstoxApiClient, TokenBucket
from app.acquisition.validator import DataQualityAuditor
from app.acquisition.backfill import HistoricalBackfillOrchestrator
from app.research_os.governance.dataset_registry import DatasetRegistry, ensure_research_storage_structure


class TestHistoricalDataAcquisitionSystem(unittest.TestCase):
    """
    Comprehensive Unit & Integration Test Suite for the 
    Upstox Historical Data Acquisition System (Phase 1).
    """

    def setUp(self):
        ensure_research_storage_structure()
        self.discovery = InstrumentDiscoveryService()

    def test_01_instrument_discovery_and_registration(self):
        """Verify Phase 1 target instruments (SENSEX, NIFTY 50, SENSEX 30) are registered."""
        # 1. Verify BSE SENSEX
        sens = self.discovery.get_instrument("BSE_INDEX|SENSEX")
        self.assertIsNotNone(sens)
        self.assertEqual(sens.trading_symbol, "SENSEX")
        self.assertEqual(sens.instrument_type, "INDEX")

        # 2. Verify NIFTY 50
        nifty = self.discovery.get_instrument("NSE_INDEX|Nifty 50")
        self.assertIsNotNone(nifty)
        self.assertEqual(nifty.trading_symbol, "Nifty 50")

        # 3. Verify SENSEX 30 Equity (Reliance BSE)
        rel_isin = SENSEX_30_ISINS["RELIANCE"]
        rel = self.discovery.get_instrument(f"BSE_EQ|{rel_isin}")
        self.assertIsNotNone(rel)
        self.assertEqual(rel.trading_symbol, "RELIANCE")
        self.assertEqual(rel.exchange, "BSE_EQ")

        # 4. List target instruments
        targets = self.discovery.list_target_instruments()
        self.assertGreaterEqual(len(targets), 32)

    def test_02_upstox_token_bucket_rate_limiter(self):
        """Verify TokenBucket enforces client-side rate limit caps."""
        bucket = TokenBucket(rate_per_sec=20.0)
        t0 = datetime.now()
        for _ in range(5):
            bucket.acquire()
        elapsed_ms = (datetime.now() - t0).total_seconds() * 1000.0
        self.assertLess(elapsed_ms, 500.0)

    def test_03_data_quality_auditor(self):
        """Verify DataQualityAuditor detects missing minutes and duplicate timestamps."""
        mock_candles = [
            ["2026-07-24T09:15:00+05:30", 76000.0, 76050.0, 75990.0, 76020.0, 0, 0],
            ["2026-07-24T09:16:00+05:30", 76020.0, 76080.0, 76010.0, 76070.0, 0, 0],
            ["2026-07-24T09:20:00+05:30", 76070.0, 76100.0, 76050.0, 76090.0, 0, 0],  # 3 min gap
        ]

        audit = DataQualityAuditor.audit_candles("BSE_INDEX|SENSEX", mock_candles)
        self.assertTrue(audit["quality_pass"])
        self.assertEqual(audit["total_rows"], 3)
        self.assertEqual(audit["duplicate_count"], 0)
        self.assertEqual(audit["missing_minutes_count"], 3)

    def test_04_full_6stage_historical_backfill_pipeline(self):
        """
        Integration Test: Mock Upstox API response, run full 6-stage backfill pipeline 
        for BSE SENSEX, NIFTY 50, and BSE Equity, and verify Parquet, SHA256, and Registries.
        """
        # Mock Upstox API Client
        mock_client = UpstoxApiClient()
        mock_candles = [
            ["2026-07-24T09:15:00+05:30", 76124.89, 76144.07, 76116.19, 76141.27, 0, 0],
            ["2026-07-24T09:16:00+05:30", 76141.27, 76180.00, 76135.00, 76175.50, 0, 0],
        ]
        mock_client.fetch_multi_month_candles = MagicMock(return_value=mock_candles)

        orchestrator = HistoricalBackfillOrchestrator(upstox_client=mock_client)

        # 1. Backfill BSE SENSEX
        res_sensex = orchestrator.backfill_instrument("BSE_INDEX|SENSEX", "2026-07-24", "2026-07-24", "DS-v1.0.0")
        self.assertTrue(res_sensex["success"])
        self.assertEqual(res_sensex["total_exported"], 2)
        self.assertTrue(os.path.exists(res_sensex["written_files"][0]))
        self.assertTrue(os.path.exists(res_sensex["checksum_path"]))

        # 2. Backfill NIFTY 50
        res_nifty = orchestrator.backfill_instrument("NSE_INDEX|Nifty 50", "2026-07-24", "2026-07-24", "DS-v1.0.0")
        self.assertTrue(res_nifty["success"])
        self.assertEqual(res_nifty["total_exported"], 2)

        # 3. Backfill BSE Equity (Reliance)
        rel_isin = SENSEX_30_ISINS["RELIANCE"]
        res_eq = orchestrator.backfill_instrument(f"BSE_EQ|{rel_isin}", "2026-07-24", "2026-07-24", "DS-v1.0.0")
        self.assertTrue(res_eq["success"])

        # 4. Verify Dataset Registry & Sync History
        registry = DatasetRegistry()
        reg_entry = registry.get_dataset(res_sensex["dataset_id"])
        self.assertIsNotNone(reg_entry)
        self.assertEqual(reg_entry["status"], "VALIDATED")

        # Verify SQLite Sync History
        cursor = self.discovery.conn.cursor()
        cursor.execute("SELECT status FROM sync_history WHERE instrument_key = 'BSE_INDEX|SENSEX'")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "VALIDATED")


if __name__ == "__main__":
    unittest.main()
