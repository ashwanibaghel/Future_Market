import tempfile
from app.research_os.evaluation.evaluation_engine import EvaluationEngine


def test_evaluation_engine_metrics_calculation():
    with tempfile.TemporaryDirectory() as tmpdir:
        eval_engine = EvaluationEngine(base_dir=tmpdir)

        # Generate synthetic decision events
        decisions = [
            {
                "decision_id": "DEC-001",
                "timestamp_utc": 1614570300,
                "spot_price": 14500.0,
                "signal": "BULLISH",
            },
            {
                "decision_id": "DEC-002",
                "timestamp_utc": 1614570360,
                "spot_price": 14520.0,  # +20 profit
                "signal": "BULLISH",
            },
            {
                "decision_id": "DEC-003",
                "timestamp_utc": 1614570420,
                "spot_price": 14510.0,  # -10 loss
                "signal": "BEARISH",
            },
            {
                "decision_id": "DEC-004",
                "timestamp_utc": 1614570480,
                "spot_price": 14490.0,  # +20 profit
                "signal": "NEUTRAL",
            },
        ]

        report = eval_engine.evaluate_session(
            session_id="SESS-EVAL-001",
            strategy_name="PCRDivergenceStrategy",
            strategy_version="ST-v1.0.0",
            decisions=decisions,
            feature_version="F-v1.0.0",
            replay_version="R-v1.0.0",
        )

        assert report.report_id == "EVAL-PCRDivergenceStrategy-SESS-EVAL-001"
        assert report.feature_version == "F-v1.0.0"
        assert report.evaluation_version == "E-v1.0.0"

        metrics = report.metrics
        assert metrics["total_trades"] == 3
        assert metrics["net_pnl"] > 0
        assert "win_rate" in metrics
        assert "max_drawdown_pct" in metrics
        assert "profit_factor" in metrics
        assert "avg_holding_time_mins" in metrics


if __name__ == "__main__":
    test_evaluation_engine_metrics_calculation()
    print("\nALL EVALUATION ENGINE TESTS PASSED SUCCESSFULLY!")
