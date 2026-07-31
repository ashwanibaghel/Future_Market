from typing import Dict, Any, List
from app.research_os.evaluation.metrics.base import BaseMetricCalculator


class DrawdownMetric(BaseMetricCalculator):
    """Calculates Peak-to-Trough Maximum Drawdown percentage and value."""

    @property
    def metric_name(self) -> str:
        return "drawdown"

    def calculate(self, decisions: List[Dict[str, Any]], price_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not decisions:
            return {"max_drawdown_pct": 0.0, "max_drawdown_value": 0.0}

        cum_pnl = 0.0
        peak = 0.0
        max_dd_val = 0.0
        max_dd_pct = 0.0

        for i in range(len(decisions) - 1):
            d = decisions[i]
            next_d = decisions[i + 1]
            signal = d.get("signal", d.get("prediction", "NEUTRAL"))
            entry_p = d.get("spot_price", 0.0)
            exit_p = next_d.get("spot_price", entry_p)

            pnl = (exit_p - entry_p) if signal == "BULLISH" else ((entry_p - exit_p) if signal == "BEARISH" else 0.0)
            cum_pnl += pnl

            if cum_pnl > peak:
                peak = cum_pnl

            dd = peak - cum_pnl
            if dd > max_dd_val:
                max_dd_val = dd
                max_dd_pct = dd / max(1.0, entry_p) * 100.0

        return {
            "max_drawdown_pct": round(max_dd_pct, 4),
            "max_drawdown_value": round(max_dd_val, 2),
        }
