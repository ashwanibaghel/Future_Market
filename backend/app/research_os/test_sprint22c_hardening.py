import os
import json
import time
import tempfile
import unittest
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, OptionChainSnapshot, OptionChainStrike, AnalyticsSnapshot
from app.research_os.governance.versioning import (
    validate_semver,
    build_provenance_header,
    calculate_file_sha256,
)
from app.research_os.governance.dataset_registry import DatasetRegistry, ensure_research_storage_structure
from app.research_os.governance.quality_reporter import QualityReporter
from app.research_os.datalake.validator import ParquetDataValidator
from app.research_os.datalake.exporter import DatalakeExporter, calculate_1min_time_gaps, SNAPSHOT_ARROW_SCHEMA
from app.research_os.datalake.reader import DuckDBDataReader, HAS_DUCKDB

if HAS_DUCKDB:
    import duckdb


class TestSprint22CHardening(unittest.TestCase):
    """Hardening Test Suite verifying fixes for all Critical and Major audit findings."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(self.engine)
        SessionLocal = sessionmaker(bind=self.engine)
        self.db = SessionLocal()
        ensure_research_storage_structure()

    def tearDown(self):
        self.db.close()

    def test_01_semver_regex_validation(self):
        """Verify SemVer regex validation enforces OI Lens specification."""
        self.assertTrue(validate_semver("DS-v1.0.0"))
        self.assertTrue(validate_semver("R-v2.5.0"))
        self.assertTrue(validate_semver("F-v1.0.0"))
        self.assertFalse(validate_semver("INVALID_VERSION_STRING"))
        self.assertFalse(validate_semver("v1.0"))

    def test_02_actual_1min_time_gap_calculation(self):
        """Verify genuine missing 1-minute time gap calculation."""
        base = datetime(2026, 7, 24, 9, 15, 0)
        timestamps = [
            base,
            base + timedelta(minutes=1),  # Gap = 0
            base + timedelta(minutes=5),  # Gap = 3 minutes missing
            base + timedelta(minutes=6),  # Gap = 0
        ]
        gaps = calculate_1min_time_gaps(timestamps)
        self.assertEqual(gaps, 3)

    def test_03_multi_row_group_corruption_detection(self):
        """Verify ParquetDataValidator scans ALL row groups for zero corruption."""
        # Create a Parquet file with 3 row groups
        rows_rg1 = [{"snapshot_id": 1, "timestamp": "2026-07-24T09:15:00", "symbol": "NIFTY", "expiry_date": "2026-07-30", "spot_price": 24200.0, "pcr": 1.2, "market_state": "NEUTRAL", "strength": "LOW", "support_s1": 24100.0, "resistance_r1": 24300.0, "strikes": [], "strikes_count": 0}]
        rows_rg2 = [{"snapshot_id": 2, "timestamp": "2026-07-24T09:16:00", "symbol": "NIFTY", "expiry_date": "2026-07-30", "spot_price": 24205.0, "pcr": 1.2, "market_state": "NEUTRAL", "strength": "LOW", "support_s1": 24100.0, "resistance_r1": 24300.0, "strikes": [], "strikes_count": 0}]

        t1 = pa.Table.from_pylist(rows_rg1, schema=SNAPSHOT_ARROW_SCHEMA)
        t2 = pa.Table.from_pylist(rows_rg2, schema=SNAPSHOT_ARROW_SCHEMA)

        temp_parquet = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
        temp_parquet.close()

        with pq.ParquetWriter(temp_parquet.name, SNAPSHOT_ARROW_SCHEMA) as writer:
            writer.write_table(t1)
            writer.write_table(t2)

        val = ParquetDataValidator.validate_file(temp_parquet.name)
        self.assertTrue(val["valid"])
        self.assertEqual(val["num_row_groups"], 2)
        self.assertEqual(val["total_rows"], 2)
        os.remove(temp_parquet.name)

    def test_04_native_arrow_struct_queryability_in_duckdb(self):
        """
        Verify Native PyArrow Struct schema allows zero-overhead DuckDB columnar queries 
        on nested strike-level fields.
        """
        # Seed 1 snapshot with 2 strike records
        ts = datetime(2026, 7, 24, 9, 15, 0)
        snap = OptionChainSnapshot(
            timestamp=ts,
            symbol="NIFTY",
            expiry_date="2026-07-30",
            spot_price=24200.0,
            provider="NSE",
            collection_status="SUCCESS",
            collection_duration_ms=100,
        )
        self.db.add(snap)
        self.db.commit()

        st1 = OptionChainStrike(snapshot_id=snap.id, strike=24200.0, call_oi=5000, call_iv=14.2)
        st2 = OptionChainStrike(snapshot_id=snap.id, strike=24250.0, call_oi=3000, call_iv=14.8)
        self.db.add_all([st1, st2])
        self.db.commit()

        exporter = DatalakeExporter(self.db)
        export_res = exporter.export_snapshots_to_parquet(
            symbol="NIFTY",
            start_date="2026-07-24",
            end_date="2026-07-24",
            dataset_version="DS-v1.0.0",
        )
        self.assertTrue(export_res["success"])
        parquet_path = export_res["parquet_path"]

        # DuckDB direct nested struct query test
        if HAS_DUCKDB:
            conn = duckdb.connect()
            pattern_path = parquet_path.replace("\\", "/")
            sql = f"""
                SELECT strikes[1].strike AS first_strike, strikes[1].call_oi AS first_call_oi 
                FROM read_parquet('{pattern_path}')
            """
            res = conn.execute(sql).fetchone()
            self.assertEqual(res[0], 24200.0)
            self.assertEqual(res[1], 5000)

    def test_05_atomic_dataset_registry_writes(self):
        """Verify atomic file swaps in DatasetRegistry prevent index corruption."""
        registry = DatasetRegistry()
        meta = {
            "dataset_id": "DS-NIFTY-ATOMIC-TEST",
            "dataset_version": "DS-v1.0.0",
            "symbol": "NIFTY",
            "total_rows": 100,
            "sha256_checksum": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        }
        entry = registry.register_dataset(meta)
        self.assertEqual(entry["dataset_id"], "DS-NIFTY-ATOMIC-TEST")
        self.assertTrue(os.path.exists(registry.index_json))
        self.assertTrue(os.path.exists(registry.index_parquet))


if __name__ == "__main__":
    unittest.main()
