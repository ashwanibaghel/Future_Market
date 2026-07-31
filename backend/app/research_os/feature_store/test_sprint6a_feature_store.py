import os
import tempfile
import pyarrow as pa
import pyarrow.parquet as pq

from app.research_os.feature_store.feature_version import DEFAULT_FEATURE_VERSION, DEFAULT_FEATURE_SCHEMA_VERSION, build_feature_metadata_header
from app.research_os.feature_store.feature_registry import FeatureRegistry
from app.research_os.feature_store.feature_store import FeatureStore
from app.research_os.features.feature_engine import FeatureEngine

TEST_FEATURE_SCHEMA = pa.schema([
    ("timestamp", pa.string()),
    ("timestamp_utc", pa.int64()),
    ("symbol", pa.string()),
    ("spot_price", pa.float64()),
    ("atm_strike", pa.float64()),
    ("pcr_volume", pa.float64()),
    ("pcr_oi", pa.float64()),
    ("oi_change_ce", pa.int64()),
    ("oi_change_pe", pa.int64()),
    ("vwap", pa.float64()),
    ("buildup_signal", pa.string()),
    ("feature_version", pa.string()),
    ("schema_version", pa.string()),
])


def test_feature_version_header():
    header = build_feature_metadata_header(feature_version="F-v1.0.0", symbol="NIFTY")
    assert header["feature_version"] == "F-v1.0.0"
    assert header["symbol"] == "NIFTY"
    assert "generation_timestamp" in header


def test_feature_store_and_registry_flow():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FeatureStore(base_dir=tmpdir)
        registry = FeatureRegistry(base_dir=tmpdir)

        table = pa.Table.from_arrays(
            [
                pa.array(["2021-03-01T09:15:00+05:30"], type=pa.string()),
                pa.array([1614570300], type=pa.int64()),
                pa.array(["NIFTY"], type=pa.string()),
                pa.array([14500.0], type=pa.float64()),
                pa.array([14500.0], type=pa.float64()),
                pa.array([1.25], type=pa.float64()),
                pa.array([1.10], type=pa.float64()),
                pa.array([500], type=pa.int64()),
                pa.array([600], type=pa.int64()),
                pa.array([14505.0], type=pa.float64()),
                pa.array(["LONG_BUILDUP"], type=pa.string()),
                pa.array(["F-v1.0.0"], type=pa.string()),
                pa.array(["FS-v1.0.0"], type=pa.string()),
            ],
            schema=TEST_FEATURE_SCHEMA,
        )

        assert not store.has_features("NIFTY", 2021, 3, "F-v1.0.0")

        # Save to Feature Store
        meta = store.save_features(table, "NIFTY", 2021, 3, "F-v1.0.0")
        assert meta["feature_dataset_id"] == "FEAT-NIFTY-F-v1.0.0-2021-03"
        assert store.has_features("NIFTY", 2021, 3, "F-v1.0.0")

        # Retrieve from Feature Store
        retrieved_table = store.get_features("NIFTY", 2021, 3, "F-v1.0.0")
        assert retrieved_table is not None
        assert retrieved_table.num_rows == 1
        assert retrieved_table.column("feature_version")[0].as_py() == "F-v1.0.0"

        # Verify Registry entry
        entries = store.registry.list_feature_datasets(symbol="NIFTY", feature_version="F-v1.0.0")
        assert len(entries) == 1
        assert entries[0]["feature_dataset_id"] == "FEAT-NIFTY-F-v1.0.0-2021-03"


def test_feature_engine_caching():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FeatureStore(base_dir=tmpdir)
        engine = FeatureEngine(feature_store=store)

        table = pa.Table.from_arrays(
            [
                pa.array(["2021-03-01T09:15:00+05:30"], type=pa.string()),
                pa.array([1614570300], type=pa.int64()),
                pa.array(["NIFTY"], type=pa.string()),
                pa.array([14500.0], type=pa.float64()),
                pa.array([14500.0], type=pa.float64()),
                pa.array([1.25], type=pa.float64()),
                pa.array([1.10], type=pa.float64()),
                pa.array([500], type=pa.int64()),
                pa.array([600], type=pa.int64()),
                pa.array([14505.0], type=pa.float64()),
                pa.array(["LONG_BUILDUP"], type=pa.string()),
                pa.array(["F-v1.0.0"], type=pa.string()),
                pa.array(["FS-v1.0.0"], type=pa.string()),
            ],
            schema=TEST_FEATURE_SCHEMA,
        )
        store.save_features(table, "NIFTY", 2021, 3, "F-v1.0.0")

        # Call get_or_compute_features (should trigger FeatureStore CACHE HIT)
        result_table = engine.get_or_compute_features("NIFTY", 2021, 3, "F-v1.0.0")
        assert result_table.num_rows == 1
        assert result_table.column("buildup_signal")[0].as_py() == "LONG_BUILDUP"


if __name__ == "__main__":
    test_feature_version_header()
    test_feature_store_and_registry_flow()
    test_feature_engine_caching()
    print("\nALL SPRINT 6A FEATURE STORE TESTS PASSED SUCCESSFULLY!")
