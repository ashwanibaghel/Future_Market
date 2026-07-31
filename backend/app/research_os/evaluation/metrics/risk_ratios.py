import math
from typing import Dict, Any, List
from app.research_os.evaluation.metrics.base import BaseMetricCalculator


class RiskRatiosMetric(BaseMetricCalculator):
    """Calculates Profit Factor, Sharpe Ratio, and Expectancy."""

    @property
    def metric_name(self) -> str:
        return "risk_ratios"

    def calculate(self, decisions: List[Dict[str, Any]], price_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not decisions:
            return {"profit_factor": 0.0, "sharpe_ratio": 0.0, "expectancy": 0.0}

        pnls = []
        gross_profit = 0.0
        gross_loss = 0.0

        for i in range(len(decisions) - 1):
            d = decisions[i]
            next_d = decisions[i + 1]
            signal = d.get("signal", d.get("prediction", "NEUTRAL"))
            entry_p = d.get("spot_price", 0.0)
            exit_p = next_d.get("spot_price", entry_p)

            pnl = (exit_p - entry_p) if signal == "BULLISH" else ((entry_p - exit_p) if signal == "BEARISH" else 0.0)
            pnls.append(pnl)
            if pnl > 0:
                gross_profit += pnl
            elif pnl < 0:
                gross_loss += abs(pnl)

        profit_factor = round(gross_profit / max(0.0001, gross_loss), 4)
        expectancy = round(sum(pnls) / max(1, len(pnls)), 2)

        # Sharpe Ratio calculation
        if len(pnls) > 1:
            mean = sum(pnls) / len(pnls)
            variance = sum((x - mean) ** 2 for x in pnls) / (len(pnls) - 1)
            std_dev = math.sqrt(variance)
            sharpe_ratio = round((mean / max(0.0001, std_dev)) * math.sqrt(252), 4)
        else:
            sharpe_ratio = 0.0

        return {
            "profit_factor": profit_factor,
            "sharpe_ratio": sharpe_ratio,
            "expectancy": expectancy,
        }
