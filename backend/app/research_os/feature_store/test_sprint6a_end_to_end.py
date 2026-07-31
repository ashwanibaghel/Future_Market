import os
import tempfile
import pyarrow as pa
import pyarrow.parquet as pq

from app.acquisition.normalizer import CANONICAL_OPTION_SCHEMA
from app.research_os.governance.dataset_registry import PARQUET_LAKE_DIR
from app.research_os.feature_store.feature_store import FeatureStore
from app.research_os.features.feature_engine import FeatureEngine
from app.research_os.replay.replay_engine import HistoricalReplayEngine
from app.research_os.strategies.pcr_strategy import PCRDivergenceStrategy
from app.research_os.decision_lake.decision_lake import DecisionLake


def test_end_to_end_canonical_to_decision_lake_flow():
    """
    Requirement 7 Integration Test:
    Verifies full quantitative research data flow:
    Canonical Dataset → Feature Engine → Feature Store → Replay Engine → Strategy Engine → Decision Lake
    Confirms:
    1. Feature Engine computes features ONCE and persists to FeatureStore.
    2. Replay Engine consumes ONLY FeatureStore outputs (0 recomputation).
    3. Strategy Engine generates predictions using FeatureStore metrics.
    4. Decision Lake records decisions with matching feature_version.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Step 1: Mock Canonical Parquet Lake dataset in temp directory
        fake_lake = os.path.join(tmpdir, "parquet_lake")
        partition_dir = os.path.join(fake_lake, "exchange=NSE_FO", "symbol=NIFTY_OPTIONS", "year=2021", "month=03")
        os.makedirs(partition_dir, exist_ok=True)
        canonical_file = os.path.join(partition_dir, "option_chain.parquet")

        # Generate synthetic canonical candles (2 timestamps: T1 baseline, T2 Long Buildup)
        canonical_table = pa.Table.from_arrays(
            [
                pa.array(["2021-03-01T09:15:00+05:30", "2021-03-01T09:15:00+05:30", "2021-03-01T09:16:00+05:30", "2021-03-01T09:16:00+05:30"], type=pa.string()),
                pa.array([1614570300, 1614570300, 1614570360, 1614570360], type=pa.int64()),
                pa.array(["NIFTY", "NIFTY", "NIFTY", "NIFTY"], type=pa.string()),
                pa.array(["ATM", "ATM", "ATM", "ATM"], type=pa.string()),
                pa.array(["CALL", "PUT", "CALL", "PUT"], type=pa.string()),
                pa.array([15000.0, 15000.0, 15010.0, 15010.0], type=pa.float64()),
                pa.array([100.0, 120.0, 102.0, 118.0], type=pa.float64()),
                pa.array([105.0, 125.0, 108.0, 122.0], type=pa.float64()),
                pa.array([95.0, 115.0, 101.0, 116.0], type=pa.float64()),
                pa.array([102.0, 122.0, 106.0, 119.0], type=pa.float64()),
                pa.array([1000, 1500, 1200, 1800], type=pa.int64()),
                pa.array([10000, 15000, 12000, 18000], type=pa.int64()),
                pa.array([15.0, 16.0, 15.2, 16.1], type=pa.float64()),
                pa.array(["DHAN", "DHAN", "DHAN", "DHAN"], type=pa.string()),
            ],
            schema=CANONICAL_OPTION_SCHEMA,
        )
        pq.write_table(canonical_table, canonical_file, compression="zstd")

        # Step 2: Initialize Feature Store & Feature Engine
        store_dir = os.path.join(tmpdir, "feature_store")
        feature_store = FeatureStore(base_dir=store_dir)
        feature_engine = FeatureEngine(feature_store=feature_store)

        # Patch PARQUET_LAKE_DIR temporarily for test execution
        import app.research_os.features.feature_engine as fe_mod
        orig_lake = fe_mod.PARQUET_LAKE_DIR
        fe_mod.PARQUET_LAKE_DIR = fake_lake

        try:
            # Step 3: Compute & Cache Features in Feature Store
            feature_table = feature_engine.get_or_compute_features("NIFTY", 2021, 3, "F-v1.0.0")
            assert feature_table.num_rows == 2
            assert feature_store.has_features("NIFTY", 2021, 3, "F-v1.0.0")

            # Verify Feature Store cached readback
            cached = feature_store.get_features("NIFTY", 2021, 3, "F-v1.0.0")
            assert cached is not None
            assert cached.num_rows == 2
            assert cached.column("pcr_volume")[0].as_py() == 1.5  # 1500 / 1000 = 1.5
            assert cached.column("buildup_signal")[1].as_py() == "LONG_BUILDUP"

            # Step 4: Replay Engine Streams Features (Zero Recomputation)
            replay = HistoricalReplayEngine(feature_store=feature_store)
            strategy = PCRDivergenceStrategy()
            decision_lake = DecisionLake(base_dir=os.path.join(tmpdir, "decision_lake"))

            decisions_created = []
            for snapshot in replay.replay_month_stream("NIFTY", 2021, 3, "F-v1.0.0"):
                pred = strategy.evaluate_snapshot(snapshot)
                if pred is not None:
                    record = decision_lake.record_decision(pred)
                    decisions_created.append(record)

            assert len(decisions_created) == 1
            assert decisions_created[0]["prediction"] == "BULLISH"
            assert decisions_created[0]["feature_version"] == "F-v1.0.0"

            # Step 5: Verify Decision Lake persistence
            lake_records = decision_lake.list_decisions()
            assert len(lake_records) == 1
            assert lake_records[0]["feature_version"] == "F-v1.0.0"

        finally:
            fe_mod.PARQUET_LAKE_DIR = orig_lake


if __name__ == "__main__":
    test_end_to_end_canonical_to_decision_lake_flow()
    print("\nEND-TO-END INTEGRATION TEST PASSED SUCCESSFULLY!")
