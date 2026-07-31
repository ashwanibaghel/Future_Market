import os
import tempfile
import pyarrow as pa
import pyarrow.parquet as pq

from app.research_os.feature_store.feature_store import FeatureStore
from app.research_os.replay.replay_config import ReplayConfig
from app.research_os.replay.replay_engine import HistoricalReplayEngine
from app.research_os.replay.replay_registry import ReplayRegistry

TEST_FEATURE_SCHEMA = pa.schema([
    ("timestamp", pa.string()),
    ("timestamp_utc", pa.int64()),
    ("symbol", pa.string()),
    ("spot_price", pa.float64()),
    ("pcr_volume", pa.float64()),
    ("buildup_signal", pa.string()),
    ("feature_version", pa.string()),
    ("schema_version", pa.string()),
])


def test_replay_navigation_api():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_dir = os.path.join(tmpdir, "feature_store")
        reg_dir = os.path.join(tmpdir, "replay_sessions")

        feature_store = FeatureStore(base_dir=store_dir)
        registry = ReplayRegistry(base_dir=reg_dir)
        engine = HistoricalReplayEngine(feature_store=feature_store, registry=registry)

        # Seed synthetic features for NIFTY 2021-03
        timestamps = [f"2021-03-01T09:{m:02d}:00+05:30" for m in range(15, 30)]
        ts_utcs = [1614570300 + (i * 60) for i in range(15)]

        table = pa.Table.from_arrays(
            [
                pa.array(timestamps, type=pa.string()),
                pa.array(ts_utcs, type=pa.int64()),
                pa.array(["NIFTY"] * 15, type=pa.string()),
                pa.array([14500.0 + i for i in range(15)], type=pa.float64()),
                pa.array([1.25] * 15, type=pa.float64()),
                pa.array(["LONG_BUILDUP"] * 15, type=pa.string()),
                pa.array(["F-v1.0.0"] * 15, type=pa.string()),
                pa.array(["FS-v1.0.0"] * 15, type=pa.string()),
            ],
            schema=TEST_FEATURE_SCHEMA,
        )
        feature_store.save_features(table, "NIFTY", 2021, 3, "F-v1.0.0")

        # Create ReplayConfig
        config = ReplayConfig(
            symbol="NIFTY",
            start_date="2021-03-01",
            end_date="2021-03-31",
            feature_version="F-v1.0.0",
        )

        session = engine.create_session("SESS-TEST-001", config)
        assert session.cursor.total_snapshots == 15

        # Test step(5)
        events = session.step(count=5)
        assert len(events) == 5
        assert session.cursor.current_index == 5
        assert events[0]["replay_timestamp"] == "2021-03-01T09:15:00+05:30"

        # Test pause()
        session.pause()
        assert session.status == "PAUSED"

        # Test seek()
        seek_success = session.seek("2021-03-01T09:25:00+05:30")
        assert seek_success
        assert session.cursor.current_index == 10

        # Step 2 more
        events2 = session.step(count=2)
        assert len(events2) == 2
        assert session.cursor.current_index == 12

        # Check telemetry stats
        stats = session.get_stats()
        assert stats.session_id == "SESS-TEST-001"
        assert stats.total_snapshots_processed == 12


if __name__ == "__main__":
    test_replay_navigation_api()
    print("\nREPLAY NAVIGATION API TEST PASSED SUCCESSFULLY!")
