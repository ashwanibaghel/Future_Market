from typing import Dict, Any, List
from app.research_os.evaluation.metrics.base import BaseMetricCalculator


class HoldingTimeMetric(BaseMetricCalculator):
    """Calculates Average Holding Time in minutes between decision entries and exits."""

    @property
    def metric_name(self) -> str:
        return "holding_time"

    def calculate(self, decisions: List[Dict[str, Any]], price_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not decisions or len(decisions) < 2:
            return {"avg_holding_time_mins": 0.0}

        durations = []
        for i in range(len(decisions) - 1):
            d = decisions[i]
            next_d = decisions[i + 1]
            t1 = d.get("timestamp_utc", 0)
            t2 = next_d.get("timestamp_utc", 0)
            if t2 > t1 > 0:
                mins = (t2 - t1) / 60.0
                durations.append(mins)

        avg_dur = round(sum(durations) / max(1, len(durations)), 2)
        return {"avg_holding_time_mins": avg_dur}
