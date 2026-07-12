from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import (
    EntryTimingEvaluation,
    ExecutionStrikeCandidate,
    ExitTimingEvaluation,
    PremiumEvolution,
    RiskEvaluation,
    TradingSignal,
)


def _readiness(label_quality: float, feature_availability: float, examples: float, replay_support: float, outcome_quality: float) -> float:
    return round(
        (label_quality * 0.30)
        + (feature_availability * 0.20)
        + (examples * 0.20)
        + (replay_support * 0.15)
        + (outcome_quality * 0.15),
        2,
    )


def get_execution_intelligence(db: Session, symbol: str | None = None) -> dict:
    signal_query = db.query(TradingSignal)
    if symbol:
        signal_query = signal_query.filter(TradingSignal.symbol == symbol.upper())
    total_signals = signal_query.count()
    resolved_signals = signal_query.filter(
        (TradingSignal.outcome_15m != "PENDING")
        | (TradingSignal.outcome_30m != "PENDING")
        | (TradingSignal.outcome_60m != "PENDING")
    ).count()

    strike_candidates = db.query(ExecutionStrikeCandidate).count()
    premium_paths = db.query(PremiumEvolution).count()
    entry_rows = db.query(EntryTimingEvaluation).count()
    exit_rows = db.query(ExitTimingEvaluation).count()
    risk_rows = db.query(RiskEvaluation).count()

    label_quality = min(100.0, (resolved_signals / max(1, total_signals)) * 100.0)
    replay_support = min(100.0, (premium_paths / max(1, total_signals)) * 100.0)
    outcome_quality = label_quality

    modules = {
        "entry_model": _readiness(label_quality, min(100.0, entry_rows / max(1, total_signals) * 100.0), min(100.0, entry_rows / 500 * 100.0), replay_support, outcome_quality),
        "exit_model": _readiness(label_quality, min(100.0, exit_rows / max(1, total_signals) * 100.0), min(100.0, exit_rows / 500 * 100.0), replay_support, outcome_quality),
        "strike_selection_model": _readiness(label_quality, min(100.0, strike_candidates / max(1, total_signals) * 100.0), min(100.0, strike_candidates / 500 * 100.0), replay_support, outcome_quality),
        "risk_manager": _readiness(label_quality, min(100.0, risk_rows / max(1, total_signals) * 100.0), min(100.0, risk_rows / 500 * 100.0), replay_support, outcome_quality),
        "position_sizing_model": _readiness(label_quality, min(100.0, risk_rows / max(1, total_signals) * 100.0), min(100.0, risk_rows / 1000 * 100.0), replay_support, outcome_quality),
    }

    blockers = []
    if strike_candidates < 500:
        blockers.append("Need at least 500 strike candidate examples.")
    if entry_rows < 500:
        blockers.append("Need at least 500 entry timing samples.")
    if exit_rows < 500:
        blockers.append("Need at least 500 exit timing samples.")
    if risk_rows < 500:
        blockers.append("Need at least 500 risk evaluation samples.")
    if replay_support < 80:
        blockers.append("Need higher premium evolution replay coverage.")

    return {
        "engine": "Execution Intelligence",
        "status": "READY" if min(modules.values()) >= 70 else ("DEGRADED" if total_signals else "BLOCKED"),
        "readiness": modules,
        "counts": {
            "signals": total_signals,
            "resolved_signals": resolved_signals,
            "strike_candidates": strike_candidates,
            "premium_evolution": premium_paths,
            "entry_timing": entry_rows,
            "exit_timing": exit_rows,
            "risk_evaluations": risk_rows,
        },
        "blockers": blockers,
        "formula": "0.30 label_quality + 0.20 feature_availability + 0.20 historical_examples + 0.15 replay_support + 0.15 outcome_quality",
    }

