from typing import Dict, Any, List
from app.research_os.evaluation.metrics.base import BaseMetricCalculator


class TradeSummaryMetric(BaseMetricCalculator):
    """Calculates Total Trades, Win Rate, Net PnL, Average Profit, and Average Loss."""

    @property
    def metric_name(self) -> str:
        return "trade_summary"

    def calculate(self, decisions: List[Dict[str, Any]], price_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not decisions:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "net_pnl": 0.0,
                "avg_profit": 0.0,
                "avg_loss": 0.0,
            }

        wins = []
        losses = []

        # Simple PnL evaluation based on signal direction and price movement
        for i in range(len(decisions) - 1):
            d = decisions[i]
            next_d = decisions[i + 1]
            signal = d.get("signal", d.get("prediction", "NEUTRAL"))
            entry_p = d.get("spot_price", 0.0)
            exit_p = next_d.get("spot_price", entry_p)

            if signal == "BULLISH":
                pnl = exit_p - entry_p
            elif signal == "BEARISH":
                pnl = entry_p - exit_p
            else:
                pnl = 0.0

            if pnl > 0:
                wins.append(pnl)
            elif pnl < 0:
                losses.append(pnl)

        total_trades = len(wins) + len(losses)
        win_rate = round(len(wins) / max(1, total_trades), 4)
        net_pnl = round(sum(wins) + sum(losses), 2)
        avg_profit = round(sum(wins) / max(1, len(wins)), 2)
        avg_loss = round(sum(losses) / max(1, len(losses)), 2)

        return {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "net_pnl": net_pnl,
            "avg_profit": avg_profit,
            "avg_loss": avg_loss,
        }
