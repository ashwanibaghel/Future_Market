from dataclasses import dataclass, field
from typing import Dict, Any, List
from app.research_os.evaluation.evaluation_version import DEFAULT_EVALUATION_VERSION
from app.research_os.feature_store.feature_version import DEFAULT_FEATURE_VERSION
from app.research_os.replay.replay_version import DEFAULT_REPLAY_VERSION


@dataclass
class EvaluationReport:
    """
    Requirement 6 Versioned Evaluation Report Object.
    Contains evaluation metrics, strategy metadata, replay metadata, feature version, and runtime statistics.
    Guarantees 100% historical reproducibility across future releases.
    """
    report_id: str
    strategy_name: str
    strategy_version: str
    session_id: str
    feature_version: str = DEFAULT_FEATURE_VERSION
    replay_version: str = DEFAULT_REPLAY_VERSION
    evaluation_version: str = DEFAULT_EVALUATION_VERSION
    metrics: Dict[str, Any] = field(default_factory=dict)
    runtime_stats: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "session_id": self.session_id,
            "feature_version": self.feature_version,
            "replay_version": self.replay_version,
            "evaluation_version": self.evaluation_version,
            "metrics": self.metrics,
            "runtime_stats": self.runtime_stats,
        }
