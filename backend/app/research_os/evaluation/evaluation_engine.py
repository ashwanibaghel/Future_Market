import os
import json
import logging
import tempfile
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import pyarrow as pa
import pyarrow.parquet as pq

from app.research_os.governance.dataset_registry import RESEARCH_STORAGE_DIR, ensure_research_storage_structure
from app.research_os.evaluation.evaluation_version import DEFAULT_EVALUATION_VERSION
from app.research_os.evaluation.evaluation_report import EvaluationReport
from app.research_os.evaluation.metrics.base import BaseMetricCalculator
from app.research_os.evaluation.metrics.trade_summary import TradeSummaryMetric
from app.research_os.evaluation.metrics.drawdown import DrawdownMetric
from app.research_os.evaluation.metrics.risk_ratios import RiskRatiosMetric
from app.research_os.evaluation.metrics.holding_time import HoldingTimeMetric

logger = logging.getLogger("research_os.evaluation.engine")

EVALUATION_STORAGE_DIR = os.path.join(RESEARCH_STORAGE_DIR, "evaluation_reports")


class EvaluationEngine:
    """
    Deliverable 5 Independent Evaluation Engine Orchestrator.
    Executes pluggable metric modules over Decision Events and generates reproducible EvaluationReports.
    Independent from Replay and Strategy implementations.
    """

    def __init__(
        self,
        base_dir: str = EVALUATION_STORAGE_DIR,
        metrics: Optional[List[BaseMetricCalculator]] = None,
    ):
        ensure_research_storage_structure()
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        self.metrics_calculators = metrics or [
            TradeSummaryMetric(),
            DrawdownMetric(),
            RiskRatiosMetric(),
            HoldingTimeMetric(),
        ]
        self.reports_json = os.path.join(self.base_dir, "evaluation_reports.json")

    def evaluate_session(
        self,
        session_id: str,
        strategy_name: str,
        strategy_version: str,
        decisions: List[Dict[str, Any]],
        feature_version: str = "F-v1.0.0",
        replay_version: str = "R-v1.0.0",
        runtime_stats: Optional[Dict[str, Any]] = None,
    ) -> EvaluationReport:
        """
        Calculates all pluggable performance metrics and generates an immutable EvaluationReport.
        """
        combined_metrics = {}
        price_history = []  # Extracted from decision metadata or spot price

        # Run each modular metric calculator
        for calc in self.metrics_calculators:
            res = calc.calculate(decisions, price_history)
            combined_metrics.update(res)

        report_id = f"EVAL-{strategy_name}-{session_id}"

        report = EvaluationReport(
            report_id=report_id,
            strategy_name=strategy_name,
            strategy_version=strategy_version,
            session_id=session_id,
            feature_version=feature_version,
            replay_version=replay_version,
            evaluation_version=DEFAULT_EVALUATION_VERSION,
            metrics=combined_metrics,
            runtime_stats=runtime_stats or {},
        )

        self._save_report_atomic(report)
        logger.info("Generated EvaluationReport '%s' (WinRate: %.2f%%, NetPnL: %.2f)", report_id, report.metrics.get("win_rate", 0.0) * 100, report.metrics.get("net_pnl", 0.0))
        return report

    def list_reports(self) -> List[Dict[str, Any]]:
        """Lists recorded evaluation reports."""
        if not os.path.exists(self.reports_json):
            return []
        try:
            with open(self.reports_json, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_report_atomic(self, report: EvaluationReport):
        existing = self.list_reports()
        filtered = [r for r in existing if r["report_id"] != report.report_id]
        filtered.append(report.to_dict())

        temp_dir = os.path.dirname(self.reports_json)
        tf = tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8")
        json.dump(filtered, tf, indent=2)
        tf.flush()
        tf.close()
        temp_name = tf.name
        try:
            os.replace(temp_name, self.reports_json)
        except PermissionError:
            with open(self.reports_json, "w", encoding="utf-8") as f:
                json.dump(filtered, f, indent=2)
            try:
                os.remove(temp_name)
            except Exception:
                pass
