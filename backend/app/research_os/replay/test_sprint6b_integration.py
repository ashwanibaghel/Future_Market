import os
import tempfile
import pyarrow as pa

from app.research_os.feature_store.feature_store import FeatureStore
from app.research_os.replay.replay_config import ReplayConfig
from app.research_os.replay.replay_engine import HistoricalReplayEngine
from app.research_os.replay.replay_registry import ReplayRegistry
from app.research_os.strategies.pcr_strategy import PCRDivergenceStrategy
from app.research_os.decision_lake.decision_lake import DecisionLake

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


def test_sprint6b_full_integration():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_dir = os.path.join(tmpdir, "feature_store")
        reg_dir = os.path.join(tmpdir, "replay_sessions")
        dec_dir = os.path.join(tmpdir, "decision_lake")

        feature_store = FeatureStore(base_dir=store_dir)
        registry = ReplayRegistry(base_dir=reg_dir)
        decision_lake = DecisionLake(base_dir=dec_dir)
        engine = HistoricalReplayEngine(feature_store=feature_store, registry=registry)

        # Seed synthetic features for NIFTY 2021-03 (10 candles)
        timestamps = [f"2021-03-01T09:{m:02d}:00+05:30" for m in range(15, 25)]
        ts_utcs = [1614570300 + (i * 60) for i in range(10)]

        table = pa.Table.from_arrays(
            [
                pa.array(timestamps, type=pa.string()),
                pa.array(ts_utcs, type=pa.int64()),
                pa.array(["NIFTY"] * 10, type=pa.string()),
                pa.array([14500.0 + i for i in range(10)], type=pa.float64()),
                pa.array([1.35] * 10, type=pa.float64()),
                pa.array(["LONG_BUILDUP"] * 10, type=pa.string()),
                pa.array(["F-v1.0.0"] * 10, type=pa.string()),
                pa.array(["FS-v1.0.0"] * 10, type=pa.string()),
            ],
            schema=TEST_FEATURE_SCHEMA,
        )
        feature_store.save_features(table, "NIFTY", 2021, 3, "F-v1.0.0")

        # Step 1: Initialize ReplayConfig & Session
        config = ReplayConfig(
            symbol="NIFTY",
            start_date="2021-03-01",
            end_date="2021-03-31",
            feature_version="F-v1.0.0",
        )

        session_id = "SESS-INTEG-001"
        session = engine.create_session(session_id, config)

        # Multi-Strategy Listeners setup
        strategy_a = PCRDivergenceStrategy()
        decisions_captured = []

        def multi_strategy_listener(event: dict):
            pred = strategy_a.evaluate_snapshot(event)
            if pred is not None:
                record = decision_lake.record_decision(pred)
                decisions_captured.append(record)

        session.register_listener(multi_strategy_listener)

        # Step 2: Run first 4 steps and pause
        session.step(count=4)
        assert session.cursor.current_index == 4
        assert len(decisions_captured) == 4

        session.pause()
        assert session.status == "PAUSED"

        # Step 3: Failure Recovery - Instantiate fresh session and resume from checkpoint
        resumed_session = engine.resume_session(session_id)
        assert resumed_session is not None
        assert resumed_session.cursor.current_index == 4
        resumed_session.register_listener(multi_strategy_listener)

        # Step 4: Resume play to completion
        for _ in resumed_session.play():
            pass

        assert resumed_session.cursor.current_index == 10
        assert resumed_session.status == "COMPLETED"
        assert len(decisions_captured) == 10

        # Step 5: Verify Decision Lake persistence
        lake_records = decision_lake.list_decisions()
        assert len(lake_records) == 10
        assert lake_records[0]["feature_version"] == "F-v1.0.0"

        # Step 6: Verify Telemetry Stats
        stats = resumed_session.get_stats()
        assert stats.total_snapshots_processed == 10
        assert stats.session_status == "COMPLETED"


if __name__ == "__main__":
    test_sprint6b_full_integration()
    print("\nSPRINT 6B FULL INTEGRATION TEST PASSED SUCCESSFULLY!")
