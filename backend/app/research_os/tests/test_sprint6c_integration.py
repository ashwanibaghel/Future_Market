import os
import tempfile
import pyarrow as pa

from app.research_os.feature_store.feature_store import FeatureStore
from app.research_os.replay.replay_config import ReplayConfig
from app.research_os.replay.replay_engine import HistoricalReplayEngine
from app.research_os.replay.replay_registry import ReplayRegistry
from app.research_os.strategy.plugins.pcr_divergence_plugin import PCRDivergencePlugin
from app.research_os.strategy.strategy_context import StrategyContext
from app.research_os.decision_lake.decision_lake import DecisionLake
from app.research_os.evaluation.evaluation_engine import EvaluationEngine
from app.research_os.tests.benchmark_fixtures import generate_benchmark_dataset


def test_sprint6c_full_end_to_end_pipeline():
    """
    Deliverable 8 Integration Test:
    Verifies full quantitative research flow:
    Replay Engine → Strategy Framework → Decision Events → Decision Lake → Evaluation Engine → EvaluationReport
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        store_dir = os.path.join(tmpdir, "feature_store")
        reg_dir = os.path.join(tmpdir, "replay_sessions")
        dec_dir = os.path.join(tmpdir, "decision_lake")
        eval_dir = os.path.join(tmpdir, "evaluation_reports")

        feature_store = FeatureStore(base_dir=store_dir)
        registry = ReplayRegistry(base_dir=reg_dir)
        decision_lake = DecisionLake(base_dir=dec_dir)
        eval_engine = EvaluationEngine(base_dir=eval_dir)
        replay_engine = HistoricalReplayEngine(feature_store=feature_store, registry=registry)

        # Step 1: Seed Deterministic Benchmark Dataset (20 snapshots)
        benchmark_table = generate_benchmark_dataset(num_snapshots=20)
        feature_store.save_features(benchmark_table, "NIFTY", 2021, 3, "F-v1.0.0")

        # Step 2: Initialize ReplayConfig & Strategy Plugin
        config = ReplayConfig(
            symbol="NIFTY",
            start_date="2021-03-01",
            end_date="2021-03-31",
            feature_version="F-v1.0.0",
        )

        session_id = "SESS-E2E-6C-001"
        session = replay_engine.create_session(session_id, config)
        strategy = PCRDivergencePlugin()
        strategy.initialize()
        strategy.on_session_start({"session_id": session_id})

        decisions_collected = []

        def strategy_listener(event: dict):
            context = StrategyContext.from_enriched_event(event)
            decision = strategy.on_snapshot(context)
            if decision is not None:
                record = decision_lake.record_decision(decision.to_dict())
                decisions_collected.append(record)

        session.register_listener(strategy_listener)

        # Step 3: Execute Replay Session to completion
        for _ in session.play():
            pass

        strategy.on_session_end({"session_id": session_id})
        strategy.shutdown()

        assert session.status == "COMPLETED"
        assert len(decisions_collected) > 0

        # Step 4: Verify Decision Lake Records
        lake_decisions = decision_lake.list_decisions()
        assert len(lake_decisions) == len(decisions_collected)
        assert lake_decisions[0]["feature_version"] == "F-v1.0.0"

        # Step 5: Evaluate Strategy Performance via Evaluation Engine
        stats = session.get_stats()
        report = eval_engine.evaluate_session(
            session_id=session_id,
            strategy_name=strategy.manifest.strategy_name,
            strategy_version=strategy.manifest.strategy_version,
            decisions=lake_decisions,
            feature_version="F-v1.0.0",
            replay_version=config.replay_version,
            runtime_stats=stats.to_dict(),
        )

        # Step 6: Verify EvaluationReport
        assert report.strategy_name == "PCRDivergenceStrategy"
        assert report.metrics["total_trades"] > 0
        assert "win_rate" in report.metrics
        assert "sharpe_ratio" in report.metrics

        reports_list = eval_engine.list_reports()
        assert len(reports_list) == 1
        assert reports_list[0]["evaluation_version"] == "E-v1.0.0"


if __name__ == "__main__":
    test_sprint6c_full_end_to_end_pipeline()
    print("\nSPRINT 6C FULL END-TO-END INTEGRATION TEST PASSED SUCCESSFULLY!")
