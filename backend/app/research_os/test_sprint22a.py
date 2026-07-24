import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, OptionChainSnapshot, OptionChainStrike, AnalyticsSnapshot
from app.research_os.governance.versioning import (
    build_provenance_header,
    calculate_bytes_sha256,
    calculate_file_sha256,
    get_git_commit_hash,
)
from app.research_os.governance.dataset_registry import (
    DatasetRegistry,
    ensure_research_storage_structure,
    RESEARCH_STORAGE_DIR,
)
from app.research_os.governance.quality_reporter import QualityReporter
from app.research_os.datalake.validator import ParquetDataValidator
from app.research_os.datalake.exporter import DatalakeExporter
from app.research_os.datalake.reader import DuckDBDataReader


class TestSprint22AFoundation(unittest.TestCase):
    """Integration & Unit Test Suite for Sprint 22A — Foundation Infrastructure."""

    def setUp(self):
        # Create an in-memory SQLite database
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(self.engine)
        SessionLocal = sessionmaker(bind=self.engine)
        self.db = SessionLocal()

        # Ensure storage structure exists
        self.dirs = ensure_research_storage_structure()

    def tearDown(self):
        self.db.close()

    def test_01_version_and_provenance(self):
        """Test SHA256 checksums, git hash, and provenance header construction."""
        sample_bytes = b"OI Lens Research Data Test Payload"
        sha256_hash = calculate_bytes_sha256(sample_bytes)
        self.assertEqual(len(sha256_hash), 64)

        git_hash = get_git_commit_hash()
        self.assertIsNotNone(git_hash)

        provenance = build_provenance_header(
            dataset_id="DS-TEST-001",
            dataset_version="DS-v1.0.0",
            sha256_checksum=sha256_hash,
        )
        self.assertIn("provenance", provenance)
        self.assertEqual(provenance["provenance"]["dataset_id"], "DS-TEST-001")
        self.assertEqual(provenance["provenance"]["sha256_checksum"], sha256_hash)
        self.assertEqual(provenance["provenance"]["provenance_status"], "VALIDATED")

    def test_02_research_storage_structure(self):
        """Verify all 8 mandatory research storage directories exist."""
        self.assertTrue(os.path.exists(RESEARCH_STORAGE_DIR))
        subdirs = [
            "parquet_lake",
            "dataset_registry",
            "quality_reports",
            "checksums",
            "experiment_registry",
            "case_library",
            "research_notebooks",
            "feature_store",
        ]
        for sub in subdirs:
            p = os.path.join(RESEARCH_STORAGE_DIR, sub)
            self.assertTrue(os.path.exists(p), f"Directory missing: {p}")

    def test_03_dataset_registry(self):
        """Test registering and retrieving dataset entries."""
        registry = DatasetRegistry()
        meta = {
            "dataset_id": "DS-NIFTY-REGTEST-001",
            "dataset_version": "DS-v1.0.0",
            "symbol": "NIFTY",
            "start_date": "2026-07-24",
            "end_date": "2026-07-24",
            "total_rows": 100,
            "total_snapshots": 100,
            "sha256_checksum": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "status": "VALIDATED",
        }
        entry = registry.register_dataset(meta)
        self.assertEqual(entry["dataset_id"], "DS-NIFTY-REGTEST-001")

        fetched = registry.get_dataset("DS-NIFTY-REGTEST-001")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["symbol"], "NIFTY")

    def test_04_quality_reporter(self):
        """Test compiling JSON and Markdown data quality reports."""
        reporter = QualityReporter()
        report = reporter.generate_report(
            dataset_id="DS-QUALITY-TEST",
            expected_rows=50,
            actual_rows=50,
            duplicate_snapshots=0,
            corrupt_rows_count=0,
            sha256_verification=True,
        )
        self.assertTrue(report["quality_pass"])
        self.assertEqual(report["status"], "PASS")
        self.assertTrue(os.path.exists(report["json_path"]))
        self.assertTrue(os.path.exists(report["md_path"]))

    def test_05_parquet_validator(self):
        """Test Parquet validator integrity checks."""
        res_nonexistent = ParquetDataValidator.validate_file("non_existent_file.parquet")
        self.assertFalse(res_nonexistent["valid"])

    def test_06_full_6stage_etl_exporter_and_reader(self):
        """
        Integration Test: Seed mock SQLite database snapshots, run 6-Stage ETL Exporter,
        verify validation, SHA256 checksum, quality report, registry, and DuckDB querying.
        """
        # 1. Seed database with 5 mock 1-minute snapshots & strikes
        base_time = datetime(2026, 7, 24, 9, 15, 0)
        for i in range(5):
            ts = base_time + timedelta(minutes=i)
            snap = OptionChainSnapshot(
                timestamp=ts,
                symbol="NIFTY",
                expiry_date="2026-07-30",
                spot_price=24200.0 + i * 5,
                provider="NSE",
                collection_status="SUCCESS",
                collection_duration_ms=120,
            )
            self.db.add(snap)
            self.db.commit()
            self.db.refresh(snap)

            # Add strike
            strike = OptionChainStrike(
                snapshot_id=snap.id,
                strike=24200.0,
                call_oi=1000 + i * 100,
                call_change_oi=50,
                call_volume=500,
                call_iv=14.5,
                call_ltp=120.0,
                put_oi=1200,
                put_change_oi=80,
                put_volume=600,
                put_iv=15.0,
                put_ltp=110.0,
            )
            self.db.add(strike)

            # Add analytics
            analytics = AnalyticsSnapshot(
                timestamp=ts,
                symbol="NIFTY",
                source_snapshot_id=snap.id,
                current_spot=snap.spot_price,
                pcr=1.2,
                market_state="LONG BUILD-UP",
                strength="HIGH",
                support=24100.0,
                resistance=24300.0,
            )
            self.db.add(analytics)
            self.db.commit()

        # 2. Run DatalakeExporter
        exporter = DatalakeExporter(self.db)
        export_result = exporter.export_snapshots_to_parquet(
            symbol="NIFTY",
            start_date="2026-07-24",
            end_date="2026-07-24",
            dataset_version="DS-v1.0.0",
        )

        self.assertTrue(export_result["success"])
        self.assertEqual(export_result["total_exported"], 5)
        self.assertTrue(os.path.exists(export_result["parquet_path"]))
        self.assertTrue(os.path.exists(export_result["checksum_path"]))

        # 3. Test DuckDBDataReader
        reader = DuckDBDataReader()
        summary = reader.get_lake_summary()
        self.assertGreater(summary["total_parquet_files"], 0)

        snapshots = reader.query_snapshots(symbol="NIFTY", year="2026", month="07", limit=10)
        self.assertGreaterEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0]["symbol"], "NIFTY")


if __name__ == "__main__":
    unittest.main()
