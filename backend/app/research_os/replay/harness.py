import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.research_os.replay.context import BlindSnapshotContext

logger = logging.getLogger("research_os.replay.harness")


@dataclass
class SimulatedSignalRecord:
    """Represents a single evaluated signal decision output during replay."""
    timestamp: str
    symbol: str
    decision: str            # 'BUY_CALL', 'BUY_PUT', 'NO_TRADE'
    score: float             # Score between 0 and 100
    reasons: List[str]
    spot_price: float
    pcr: float
    market_state: str
    support_s1: float
    resistance_r1: float


@dataclass
class SimulationRunResult:
    """Represents the complete simulation run output artifact."""
    run_id: str
    symbol: str
    start_time: str
    end_time: str
    total_ticks_evaluated: int
    signals_generated_count: int
    buy_call_count: int
    buy_put_count: int
    no_trade_count: int
    signal_records: List[SimulatedSignalRecord] = field(default_factory=list)


class SimulationHarness:
    """
    Automated Rule Simulation Harness.
    Executes Production V2.5 Quantitative Rules using ONLY BlindSnapshotContext.
    """

    def evaluate_tick(self, context: BlindSnapshotContext, symbol: str) -> SimulatedSignalRecord:
        """
        Evaluates quantitative rules for a single minute tick.
        Strictly reads data through context (no look-ahead allowed).
        """
        snapshot = context.get_snapshot(symbol=symbol)
        mkt = context.get_market_state(symbol=symbol)
        current_ts = context.current_time.isoformat()

        if not snapshot:
            return SimulatedSignalRecord(
                timestamp=current_ts,
                symbol=symbol,
                decision="NO_TRADE",
                score=0.0,
                reasons=["No snapshot available at timestamp"],
                spot_price=0.0,
                pcr=1.0,
                market_state="NEUTRAL",
                support_s1=0.0,
                resistance_r1=0.0,
            )

        spot = snapshot.get("spot_price", 0.0)
        pcr = mkt.get("pcr", 1.0)
        state = mkt.get("market_state", "NEUTRAL")
        support = mkt.get("support_s1", 0.0)
        resistance = mkt.get("resistance_r1", 0.0)

        # Retrieve 3-minute history for PCR trend calculation
        history = context.get_history(symbol=symbol, minutes=3)
        reasons = []
        score = 50.0
        decision = "NO_TRADE"

        # Check PCR Velocity
        if len(history) >= 2:
            prev_pcr = history[-2].get("pcr", pcr)
            pcr_change = pcr - prev_pcr
            if pcr_change > 0.02:
                score += 15.0
                reasons.append(f"PCR increasing (+{pcr_change:.2f})")
            elif pcr_change < -0.02:
                score -= 15.0
                reasons.append(f"PCR decreasing ({pcr_change:.2f})")

        # Check Market State
        if "LONG BUILD-UP" in state or "SHORT COVERING" in state:
            score += 20.0
            reasons.append(f"Bullish state: {state}")
        elif "SHORT BUILD-UP" in state or "LONG UNWINDING" in state:
            score -= 20.0
            reasons.append(f"Bearish state: {state}")

        # Check Support / Resistance Proximity
        if support > 0 and (spot - support) <= (spot * 0.002):
            score += 15.0
            reasons.append(f"Near Support S1 ({support})")
        elif resistance > 0 and (resistance - spot) <= (spot * 0.002):
            score -= 15.0
            reasons.append(f"Near Resistance R1 ({resistance})")

        # Clamp Score between 0 and 100
        score = max(0.0, min(100.0, score))

        # Final Decision Thresholds
        if score >= 70.0:
            decision = "BUY_CALL"
        elif score <= 30.0:
            decision = "BUY_PUT"
        else:
            decision = "NO_TRADE"

        return SimulatedSignalRecord(
            timestamp=current_ts,
            symbol=symbol,
            decision=decision,
            score=score,
            reasons=reasons,
            spot_price=spot,
            pcr=pcr,
            market_state=state,
            support_s1=support,
            resistance_r1=resistance,
        )
