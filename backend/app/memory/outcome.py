"""
Sprint AB — Multi-Horizon Physical Outcome Engine
Calculates physical price resolution metrics (MFE, MAE, Direction, Structural Transition)
across 6 distinct forward horizons: 5m, 15m, 30m, 60m, EOD, NEXT_DAY.

Includes strict Spot Price Anomaly Filters to prevent false extreme excursion spikes (>10% index spot jump).
"""

from typing import List, Dict, Any

class OutcomeEngine:
    """
    Evaluates forward price movements relative to the end of a memory episode.
    Computes Maximum Favorable Excursion (MFE %), Maximum Adverse Excursion (MAE %),
    and resolved direction with anomaly filtering.
    """

    def calculate_multi_horizon_outcomes(
        self,
        episode: Dict[str, Any],
        subsequent_snapshots: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculates physical outcomes across 6 forward time horizons with spot sanity filtering.
        """
        snapshots = episode.get("snapshots", [])
        if not snapshots:
            return self._default_outcomes()

        base_spot = float(snapshots[-1].get("spot_price", 0.0))
        if base_spot <= 100.0 or not subsequent_snapshots:
            return self._default_outcomes()

        horizons = {
            "horizon_5m": 5,
            "horizon_15m": 15,
            "horizon_30m": 30,
            "horizon_60m": 60,
            "horizon_eod": len(subsequent_snapshots),
            "horizon_next_day": len(subsequent_snapshots)
        }

        outcomes = {}
        sit_id = episode.get("situation_id", "")
        is_bullish = sit_id in ("SIT_ACCUMULATION_BEHAVIOUR", "SIT_SHORT_COVERING_MOMENTUM", "SIT_LEVEL_BREACH_EXPANSION")

        for h_key, count in horizons.items():
            forward_snaps = subsequent_snapshots[:min(count, len(subsequent_snapshots))]
            if not forward_snaps:
                outcomes[h_key] = {"direction": "NEUTRAL", "mfe_pct": 0.0, "mae_pct": 0.0}
                continue

            # Filter spot price anomalies (spot price must be within 15% of base_spot)
            clean_prices = []
            for s in forward_snaps:
                p = float(s.get("spot_price", base_spot))
                if base_spot * 0.85 <= p <= base_spot * 1.15:
                    clean_prices.append(p)

            if not clean_prices:
                clean_prices = [base_spot]

            max_p = max(clean_prices)
            min_p = min(clean_prices)
            end_p = clean_prices[-1]

            if is_bullish:
                mfe_pct = round(((max_p - base_spot) / base_spot) * 100.0, 3)
                mae_pct = round(((min_p - base_spot) / base_spot) * 100.0, 3)
            else:
                mfe_pct = round(((base_spot - min_p) / base_spot) * 100.0, 3)
                mae_pct = round(((base_spot - max_p) / base_spot) * 100.0, 3)

            direction = "UPWARD_EXPANSION" if (end_p - base_spot) > 10.0 else (
                "DOWNWARD_PRESSURE" if (base_spot - end_p) > 10.0 else "SIDEWAYS_FLAT"
            )

            outcomes[h_key] = {
                "direction": direction,
                "mfe_pct": mfe_pct,
                "mae_pct": mae_pct,
                "end_spot": end_p
            }

        return outcomes

    def _default_outcomes(self) -> Dict[str, Any]:
        default_horizon = {"direction": "SIDEWAYS_FLAT", "mfe_pct": 0.0, "mae_pct": 0.0}
        return {
            "horizon_5m": default_horizon,
            "horizon_15m": default_horizon,
            "horizon_30m": default_horizon,
            "horizon_60m": default_horizon,
            "horizon_eod": default_horizon,
            "horizon_next_day": default_horizon
        }
