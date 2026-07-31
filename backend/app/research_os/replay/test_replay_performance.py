import os
import time
import tempfile
import pyarrow as pa

from app.research_os.feature_store.feature_store import FeatureStore
from app.research_os.replay.replay_config import ReplayConfig
from app.research_os.replay.replay_engine import HistoricalReplayEngine

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


def test_replay_performance_benchmark():
    """Verifies sub-millisecond playback throughput exceeding 10,000 snapshots/sec."""
    with tempfile.TemporaryDirectory() as tmpdir:
        feature_store = FeatureStore(base_dir=tmpdir)
        engine = HistoricalReplayEngine(feature_store=feature_store)

        # Seed 15,000 synthetic feature snapshots
        num_rows = 15000
        timestamps = [f"2021-03-01T09:{i % 60:02d}:00+05:30" for i in range(num_rows)]
        ts_utcs = [1614570300 + i for i in range(num_rows)]

        table = pa.Table.from_arrays(
            [
                pa.array(timestamps, type=pa.string()),
                pa.array(ts_utcs, type=pa.int64()),
                pa.array(["NIFTY"] * num_rows, type=pa.string()),
                pa.array([14500.0] * num_rows, type=pa.float64()),
                pa.array([1.25] * num_rows, type=pa.float64()),
                pa.array(["LONG_BUILDUP"] * num_rows, type=pa.string()),
                pa.array(["F-v1.0.0"] * num_rows, type=pa.string()),
                pa.array(["FS-v1.0.0"] * num_rows, type=pa.string()),
            ],
            schema=TEST_FEATURE_SCHEMA,
        )
        feature_store.save_features(table, "NIFTY", 2021, 3, "F-v1.0.0")

        config = ReplayConfig(
            symbol="NIFTY",
            start_date="2021-03-01",
            end_date="2021-03-31",
            feature_version="F-v1.0.0",
            replay_speed=0.0,
        )
        session = engine.create_session("SESS-PERF-001", config)

        t0 = time.monotonic()
        count = 0
        for _ in session.play():
            count += 1
        t1 = time.monotonic()

        elapsed = max(0.0001, t1 - t0)
        throughput = count / elapsed

        print(f"\n[PERFORMANCE BENCHMARK] Processed {count} snapshots in {elapsed:.4f}s ({throughput:.2f} snapshots/sec)")
        assert count == num_rows
        assert throughput > 10000, f"Performance Benchmark Failed: {throughput:.2f} snapshots/sec < 10,000 target"


if __name__ == "__main__":
    test_replay_performance_benchmark()
    print("\nREPLAY PERFORMANCE BENCHMARK PASSED SUCCESSFULLY!")
