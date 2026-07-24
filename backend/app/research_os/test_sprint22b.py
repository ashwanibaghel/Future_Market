import os
import json
import time
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, OptionChainSnapshot, OptionChainStrike, AnalyticsSnapshot
from app.research_os.governance.versioning import calculate_file_sha256
from app.research_os.governance.dataset_registry import DatasetRegistry, ensure_research_storage_structure
from app.research_os.datalake.validator import ParquetDataValidator
from app.research_os.datalake.exporter import DatalakeExporter
from app.research_os.datalake.reader import DuckDBDataReader


class TestSprint22BValidation(unittest.TestCase):
    """Rigorous CTO Validation Test Suite for Sprint 22B."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(self.engine)
        SessionLocal = sessionmaker(bind=self.engine)
        self.db = SessionLocal()
        ensure_research_storage_structure()

        # Seed 50 mock 1-minute snapshots to perform validation benchmarks
        base_time = datetime(2026, 7, 24, 9, 15, 0)
        for i in range(50):
            ts = base_time + timedelta(minutes=i)
            snap = OptionChainSnapshot(
                timestamp=ts,
                symbol="NIFTY",
                expiry_date="2026-07-30",
                spot_price=24200.0 + (i * 2.5),
                provider="NSE",
                collection_status="SUCCESS",
                collection_duration_ms=100 + (i % 20),
            )
            self.db.add(snap)
            self.db.commit()
            self.db.refresh(snap)

            # Add strike
            strike = OptionChainStrike(
                snapshot_id=snap.id,
                strike=24200.0,
                call_oi=5000 + i * 50,
                call_change_oi=120,
                call_volume=2000,
                call_iv=14.0 + (i * 0.1),
                call_ltp=150.0 - (i * 0.5),
                put_oi=6000 + i * 40,
                put_change_oi=200,
                put_volume=2500,
                put_iv=14.5 + (i * 0.1),
                put_ltp=90.0 + (i * 0.5),
            )
            self.db.add(strike)

            analytics = AnalyticsSnapshot(
                timestamp=ts,
                symbol="NIFTY",
                source_snapshot_id=snap.id,
                current_spot=snap.spot_price,
                pcr=1.25,
                market_state="LONG BUILD-UP" if i % 2 == 0 else "SHORT COVERING",
                strength="HIGH",
                support=24100.0,
                resistance=24300.0,
            )
            self.db.add(analytics)
            self.db.commit()

        # Run Exporter once
        self.exporter = DatalakeExporter(self.db)
        self.export_res = self.exporter.export_snapshots_to_parquet(
            symbol="NIFTY",
            start_date="2026-07-24",
            end_date="2026-07-24",
            dataset_version="DS-v1.0.0",
        )

    def tearDown(self):
        self.db.close()

    def test_01_row_count_parity(self):
        """CTO Check: SQLite row count == Parquet row count (100% Parity)."""
        sqlite_count = self.db.query(OptionChainSnapshot).filter(OptionChainSnapshot.symbol == "NIFTY").count()
        parquet_rows = self.export_res["total_exported"]
        self.assertEqual(sqlite_count, parquet_rows, f"Parity mismatch: SQLite={sqlite_count}, Parquet={parquet_rows}")

    def test_02_snapshot_parity_sample_check(self):
        """CTO Check: Random snapshot data comparison between SQLite and Parquet Lake."""
        reader = DuckDBDataReader()
        parquet_snaps = reader.query_snapshots(symbol="NIFTY", year="2026", month="07", limit=50)
        self.assertEqual(len(parquet_snaps), 50)

        # Check spot price of 10th snapshot
        tenth_sqlite = self.db.query(OptionChainSnapshot).order_by(OptionChainSnapshot.timestamp.asc()).offset(9).first()
        tenth_parquet = parquet_snaps[9]

        self.assertEqual(tenth_parquet["symbol"], tenth_sqlite.symbol)
        self.assertAlmostEqual(tenth_parquet["spot_price"], tenth_sqlite.spot_price, places=2)

    def test_03_duckdb_latency_benchmark(self):
        """CTO Check: DuckDB query latency under 500ms benchmark."""
        reader = DuckDBDataReader()
        t0 = time.perf_counter()
        snaps = reader.query_snapshots(symbol="NIFTY", year="2026", month="07", limit=1000)
        t_elapsed_ms = (time.perf_counter() - t0) * 1000.0
        
        self.assertLess(t_elapsed_ms, 500.0, f"DuckDB query latency too high: {t_elapsed_ms:.2f} ms")

    def test_04_sha256_checksum_verification(self):
        """CTO Check: SHA256 file checksum verification matches recorded provenance hash."""
        parquet_path = self.export_res["parquet_path"]
        calculated_sha = calculate_file_sha256(parquet_path)
        recorded_sha = self.export_res["provenance"]["provenance"]["sha256_checksum"]
        self.assertEqual(calculated_sha, recorded_sha)

    def test_05_corrupt_file_detection(self):
        """CTO Check: Corrupt or damaged Parquet file detector."""
        temp_corrupt = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
        temp_corrupt.write(b"CORRUPT_INVALID_PARQUET_HEADER_DATA")
        temp_corrupt.close()

        val_res = ParquetDataValidator.validate_file(temp_corrupt.name)
        self.assertFalse(val_res["valid"])
        os.remove(temp_corrupt.name)

    def test_06_dataset_registry_status(self):
        """CTO Check: Dataset registry status is marked VALIDATED."""
        registry = DatasetRegistry()
        entry = registry.get_dataset(self.export_res["dataset_id"])
        self.assertIsNotNone(entry)
        self.assertEqual(entry["status"], "VALIDATED")
        self.assertEqual(entry["total_rows"], 50)


if __name__ == "__main__":
    unittest.main()
