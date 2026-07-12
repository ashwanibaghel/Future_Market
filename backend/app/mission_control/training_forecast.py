from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.db.models import (
    EntryTimingEvaluation,
    ExecutionStrikeCandidate,
    ExitTimingEvaluation,
    MLFeatureSnapshot,
    PremiumEvolution,
    RiskEvaluation,
)


FIRST_MODEL_TARGET_SAMPLES = 1000
FIRST_MODEL_TARGET_FULL_LABELS = 800
FIRST_MODEL_TARGET_SESSIONS = 10
ROLLING_WINDOW_DAYS = 5


MODEL_TARGETS = [
    {
        "key": "pattern_direction_v1",
        "name": "Pattern Direction Model v1",
        "priority": 1,
        "target_samples": 1000,
        "target_full_labels": 800,
        "target_market_sessions": 10,
        "extra_current": "feature_samples",
        "extra_target": 0,
    },
    {
        "key": "direction_model_v1",
        "name": "Direction Model v1",
        "priority": 2,
        "target_samples": 2000,
        "target_full_labels": 1600,
        "target_market_sessions": 20,
        "extra_current": "feature_samples",
        "extra_target": 0,
    },
    {
        "key": "strike_selection_v1",
        "name": "Strike Selection Model v1",
        "priority": 3,
        "target_samples": 2500,
        "target_full_labels": 1800,
        "target_market_sessions": 25,
        "extra_current": "strike_candidates",
        "extra_target": 500,
    },
    {
        "key": "entry_model_v1",
        "name": "Entry Timing Model v1",
        "priority": 4,
        "target_samples": 3000,
        "target_full_labels": 2200,
        "target_market_sessions": 30,
        "extra_current": "entry_rows",
        "extra_target": 500,
    },
    {
        "key": "exit_model_v1",
        "name": "Exit Timing Model v1",
        "priority": 5,
        "target_samples": 3000,
        "target_full_labels": 2200,
        "target_market_sessions": 30,
        "extra_current": "exit_rows",
        "extra_target": 500,
    },
    {
        "key": "risk_model_v1",
        "name": "Risk Manager Model v1",
        "priority": 6,
        "target_samples": 3500,
        "target_full_labels": 2500,
        "target_market_sessions": 35,
        "extra_current": "risk_rows",
        "extra_target": 500,
    },
    {
        "key": "position_sizing_v1",
        "name": "Position Sizing Model v1",
        "priority": 7,
        "target_samples": 5000,
        "target_full_labels": 3500,
        "target_market_sessions": 50,
        "extra_current": "risk_rows",
        "extra_target": 1000,
    },
]


def _next_market_day(start: date) -> date:
    candidate = start + timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def _add_market_days(start: date, days: int) -> date:
    current = start
    for _ in range(max(0, days)):
        current = _next_market_day(current)
    return current


def _ceil_div(needed: float, rate: float) -> int:
    if needed <= 0:
        return 0
    return int((needed + max(1.0, rate) - 1) // max(1.0, rate))


def _pct(numerator: float, denominator: float) -> float:
    return round((numerator / denominator * 100.0), 2) if denominator else 0.0


def _window_date(today: date, market_days: int) -> str:
    return _add_market_days(today, market_days).isoformat()


def _accuracy_range(base_score: float, boost: float = 0.0) -> dict:
    center = max(35.0, min(82.0, base_score + boost))
    low = max(30.0, center - 2.0)
    high = min(88.0, center + 2.0)
    return {"low": round(low, 1), "high": round(high, 1), "center": round(center, 1)}


def _gate(status: bool, key: str, label: str, value: float, target: float, missing: str) -> dict:
    return {
        "key": key,
        "label": label,
        "passed": status,
        "value": round(float(value), 2),
        "target": round(float(target), 2),
        "missing": "" if status else missing,
    }


def _model_forecast(
    target: dict,
    today: date,
    total_samples: int,
    full_labels: int,
    market_days: int,
    rates: dict,
    extra_counts: dict[str, int],
    gates: list[dict],
    quality_score: float,
) -> dict:
    samples_needed = max(0, int(target["target_samples"]) - total_samples)
    labels_needed = max(0, int(target["target_full_labels"]) - full_labels)
    sessions_needed = max(0, int(target["target_market_sessions"]) - market_days)
    extra_key = target["extra_current"]
    extra_target = int(target["extra_target"])
    extra_current = extra_counts.get(extra_key, total_samples if extra_key == "feature_samples" else 0)
    extra_needed = max(0, extra_target - extra_current)

    forecast_windows = {}
    for window_name, rate_key, confidence in (
        ("optimistic", "optimistic", rates["confidence"] + 8),
        ("expected", "expected", rates["confidence"]),
        ("conservative", "conservative", max(35.0, rates["confidence"] - 10)),
    ):
        sample_rate = rates[rate_key]["samples_per_day"]
        label_rate = rates[rate_key]["full_labels_per_day"]
        extra_rate = max(1.0, sample_rate * 0.20)
        days_for_samples = _ceil_div(samples_needed, sample_rate)
        days_for_labels = _ceil_div(labels_needed, label_rate)
        days_for_extra = _ceil_div(extra_needed, extra_rate) if extra_target else 0
        days_needed = max(days_for_samples, days_for_labels, sessions_needed, days_for_extra)
        forecast_windows[window_name] = {
            "training_date": _window_date(today, days_needed),
            "market_days_needed": days_needed,
            "confidence": round(max(0.0, min(100.0, confidence)), 1),
            "daily_samples_rate": round(sample_rate, 2),
            "daily_labels_rate": round(label_rate, 2),
        }
    ready = samples_needed == 0 and labels_needed == 0 and sessions_needed == 0 and extra_needed == 0

    blockers = []
    if samples_needed:
        blockers.append(f"{samples_needed} more feature samples")
    if labels_needed:
        blockers.append(f"{labels_needed} more full labels")
    if sessions_needed:
        blockers.append(f"{sessions_needed} more market sessions")
    if extra_needed:
        blockers.append(f"{extra_needed} more {extra_key.replace('_', ' ')}")

    gate_penalty = sum(10 for gate in gates if not gate["passed"])
    sample_progress = min(100.0, _pct(total_samples, target["target_samples"]))
    label_progress = min(100.0, _pct(full_labels, target["target_full_labels"]))
    readiness_score = round((sample_progress * 0.25) + (label_progress * 0.30) + (quality_score * 0.25) + (max(0.0, 100.0 - gate_penalty) * 0.20), 2)
    accuracy_now = _accuracy_range(45.0 + readiness_score * 0.25)
    accuracy_after_5_days = _accuracy_range(45.0 + min(100.0, readiness_score + 8.0) * 0.25, 3.0)
    accuracy_after_expiry = _accuracy_range(45.0 + min(100.0, readiness_score + 16.0) * 0.25, 5.0)

    return {
        "key": target["key"],
        "name": target["name"],
        "priority": target["priority"],
        "ready": ready,
        "training_date": today.isoformat() if ready else forecast_windows["expected"]["training_date"],
        "market_days_needed": 0 if ready else forecast_windows["expected"]["market_days_needed"],
        "forecast_windows": forecast_windows,
        "readiness_score": readiness_score,
        "target_samples": target["target_samples"],
        "current_samples": total_samples,
        "target_full_labels": target["target_full_labels"],
        "current_full_labels": full_labels,
        "target_market_sessions": target["target_market_sessions"],
        "current_market_sessions": market_days,
        "extra_requirement": extra_key,
        "extra_target": extra_target,
        "extra_current": extra_current,
        "readiness_gates": gates,
        "training_quality_estimate": {
            "if_trained_today": accuracy_now,
            "after_5_more_trading_days": accuracy_after_5_days,
            "after_monthly_expiry_cycle": accuracy_after_expiry,
            "basis": "Estimated from sample progress, label coverage, dataset health, feature completeness, replay support, expiry coverage, and class balance.",
        },
        "justification": {
            "ready": ready,
            "summary": "Ready for training." if ready else "Not ready yet because one or more training gates are failing.",
            "missing_data": blockers,
            "failed_gates": [gate for gate in gates if not gate["passed"]],
        },
        "blockers": blockers,
    }


def get_training_forecast(db: Session, symbol: str | None = None) -> dict:
    # Model training uses the combined research dataset across symbols.
    # The symbol argument is intentionally ignored so the forecast does not
    # jump to multi-year dates when the UI has a single symbol selected.
    query = db.query(MLFeatureSnapshot)

    total_samples = query.count()
    full_labels = query.filter(MLFeatureSnapshot.label_quality == "FULL").count()
    completed_labels = query.filter(MLFeatureSnapshot.status == "COMPLETED").count()
    market_days = query.with_entities(MLFeatureSnapshot.market_date).filter(
        MLFeatureSnapshot.market_date.isnot(None)
    ).distinct().count()
    rows = query.all()
    expiry_values = {row.expiry_date for row in rows if row.expiry_date}
    expiry_coverage = min(100.0, len(expiry_values) / 4 * 100.0)
    class_counts = Counter()
    for row in rows:
        for direction in (row.direction_15m, row.direction_30m, row.direction_60m):
            if direction in ("UP", "DOWN", "SIDEWAYS"):
                class_counts[direction] += 1
    class_total = sum(class_counts.values())
    class_balance = 0.0
    if class_total:
        percentages = [(class_counts[key] / class_total) * 100.0 for key in ("UP", "DOWN", "SIDEWAYS")]
        class_balance = max(0.0, 100.0 - (max(percentages) - min(percentages)))

    missing_iv = sum(1 for row in rows if row.average_iv in (None, 0))
    missing_pcr = sum(1 for row in rows if row.pcr is None)
    feature_completeness = max(0.0, 100.0 - ((missing_iv / max(1, total_samples)) * 70.0) - ((missing_pcr / max(1, total_samples)) * 30.0))
    avg_quality = round(sum((row.data_quality_score or 0) for row in rows) / len(rows), 2) if rows else 0.0
    replay_validation = min(100.0, db.query(PremiumEvolution).count() / max(1, total_samples) * 100.0)
    extra_counts = {
        "feature_samples": total_samples,
        "strike_candidates": db.query(ExecutionStrikeCandidate).count(),
        "premium_paths": db.query(PremiumEvolution).count(),
        "entry_rows": db.query(EntryTimingEvaluation).count(),
        "exit_rows": db.query(ExitTimingEvaluation).count(),
        "risk_rows": db.query(RiskEvaluation).count(),
    }

    per_day_rows = query.with_entities(
        MLFeatureSnapshot.market_date,
        func.count(MLFeatureSnapshot.id),
        func.sum(case((MLFeatureSnapshot.label_quality == "FULL", 1), else_=0)),
    ).filter(MLFeatureSnapshot.market_date.isnot(None)).group_by(MLFeatureSnapshot.market_date).all()
    per_day_rows = sorted(per_day_rows, key=lambda row: str(row[0]))
    recent_rows = per_day_rows[-ROLLING_WINDOW_DAYS:]
    avg_samples_per_market_day = round(
        sum(count for _, count, _ in per_day_rows) / len(per_day_rows), 2,
    ) if per_day_rows else 0.0
    rolling_samples_per_day = round(sum(count for _, count, _ in recent_rows) / len(recent_rows), 2) if recent_rows else 0.0
    rolling_labels_per_day = round(sum(int(labels or 0) for _, _, labels in recent_rows) / len(recent_rows), 2) if recent_rows else 0.0
    if rolling_labels_per_day == 0 and rolling_samples_per_day:
        rolling_labels_per_day = round(rolling_samples_per_day * ((full_labels / total_samples) if total_samples else 0.0), 2)
    fallback_samples = max(1.0, avg_samples_per_market_day or rolling_samples_per_day or 1.0)
    fallback_labels = max(1.0, rolling_labels_per_day or fallback_samples * 0.25)
    rates = {
        "optimistic": {
            "samples_per_day": max(1.0, rolling_samples_per_day * 1.25 if rolling_samples_per_day else fallback_samples),
            "full_labels_per_day": max(1.0, rolling_labels_per_day * 1.25 if rolling_labels_per_day else fallback_labels),
        },
        "expected": {
            "samples_per_day": max(1.0, rolling_samples_per_day or fallback_samples),
            "full_labels_per_day": max(1.0, rolling_labels_per_day or fallback_labels),
        },
        "conservative": {
            "samples_per_day": max(1.0, (rolling_samples_per_day or fallback_samples) * 0.65),
            "full_labels_per_day": max(1.0, (rolling_labels_per_day or fallback_labels) * 0.65),
        },
        "confidence": min(92.0, 45.0 + min(len(recent_rows), ROLLING_WINDOW_DAYS) * 8.0 + min(market_days, 10) * 1.5),
    }

    samples_needed = max(0, FIRST_MODEL_TARGET_SAMPLES - total_samples)
    labels_needed = max(0, FIRST_MODEL_TARGET_FULL_LABELS - full_labels)
    sessions_needed = max(0, FIRST_MODEL_TARGET_SESSIONS - market_days)

    label_rate = (full_labels / total_samples) if total_samples else 0.0
    days_for_samples = _ceil_div(samples_needed, rates["expected"]["samples_per_day"])
    days_for_labels = _ceil_div(labels_needed, rates["expected"]["full_labels_per_day"])
    required_market_days = max(days_for_samples, days_for_labels, sessions_needed)
    forecast_date = _add_market_days(datetime.utcnow().date(), required_market_days)

    ready_now = (
        total_samples >= FIRST_MODEL_TARGET_SAMPLES
        and full_labels >= FIRST_MODEL_TARGET_FULL_LABELS
        and market_days >= FIRST_MODEL_TARGET_SESSIONS
    )

    blockers = []
    if samples_needed:
        blockers.append(f"Need {samples_needed} more feature samples.")
    if labels_needed:
        blockers.append(f"Need {labels_needed} more full labels.")
    if sessions_needed:
        blockers.append(f"Need {sessions_needed} more market sessions.")
    if avg_samples_per_market_day == 0:
        blockers.append("Need at least one completed market day to estimate daily collection speed.")

    today = datetime.utcnow().date()
    base_gates = [
        _gate(total_samples >= FIRST_MODEL_TARGET_SAMPLES, "sample_count", "Sample count", total_samples, FIRST_MODEL_TARGET_SAMPLES, f"{samples_needed} more samples"),
        _gate(full_labels >= FIRST_MODEL_TARGET_FULL_LABELS, "label_completion", "Full label completion", full_labels, FIRST_MODEL_TARGET_FULL_LABELS, f"{labels_needed} more full labels"),
        _gate(class_balance >= 65, "class_balance", "Class balance", class_balance, 65, "Need more balanced UP/DOWN/SIDEWAYS labels"),
        _gate(expiry_coverage >= 75, "expiry_coverage", "Expiry coverage", expiry_coverage, 75, "Need more weekly/monthly expiry coverage"),
        _gate(replay_validation >= 50, "replay_validation", "Replay validation", replay_validation, 50, "Need premium evolution/replay outcomes"),
        _gate(avg_quality >= 70, "dataset_health", "Dataset health", avg_quality, 70, "Need cleaner feature rows"),
        _gate(feature_completeness >= 75, "feature_completeness", "Feature completeness", feature_completeness, 75, "Need IV/PCR/Greeks completeness"),
    ]
    quality_score = round((avg_quality * 0.35) + (feature_completeness * 0.25) + (class_balance * 0.15) + (expiry_coverage * 0.15) + (replay_validation * 0.10), 2)
    model_forecasts = [
        _model_forecast(
            target,
            today,
            total_samples,
            full_labels,
            market_days,
            rates,
            extra_counts,
            base_gates,
            quality_score,
        )
        for target in MODEL_TARGETS
    ]
    first_pending = next((model for model in model_forecasts if not model["ready"]), model_forecasts[0])
    next_target = {
        "title": f"Make {first_pending['name']} trainable",
        "model": first_pending["name"],
        "training_date": first_pending["training_date"],
        "market_days_needed": first_pending["market_days_needed"],
        "why_this_first": "This is the highest-priority model that is not ready yet.",
        "blockers": first_pending["blockers"],
        "action": (
            "Collect more labeled market sessions first."
            if any("market sessions" in item or "full labels" in item for item in first_pending["blockers"])
            else "Complete the model-specific execution dataset."
        ),
    }

    return {
        "engine": "ML Training Forecast",
        "status": "READY" if ready_now else ("DEGRADED" if total_samples else "BLOCKED"),
        "training_scope": "COMBINED_ALL_SYMBOLS",
        "scope_note": "NIFTY, SENSEX, BANKNIFTY and future symbols are combined for shared model training.",
        "ignored_symbol_filter": symbol.upper() if symbol else None,
        "ready_now": ready_now,
        "first_model_name": "Pattern Direction Model v1",
        "target_samples": FIRST_MODEL_TARGET_SAMPLES,
        "target_full_labels": FIRST_MODEL_TARGET_FULL_LABELS,
        "target_market_sessions": FIRST_MODEL_TARGET_SESSIONS,
        "current_samples": total_samples,
        "current_full_labels": full_labels,
        "current_completed_labels": completed_labels,
        "current_market_sessions": market_days,
        "avg_samples_per_market_day": avg_samples_per_market_day,
        "rolling_window_days": ROLLING_WINDOW_DAYS,
        "rolling_samples_per_day": rolling_samples_per_day,
        "rolling_full_labels_per_day": rolling_labels_per_day,
        "forecast_rates": rates,
        "readiness_gates": base_gates,
        "quality_score": quality_score,
        "market_days_needed": required_market_days,
        "forecast_training_date": datetime.utcnow().date().isoformat() if ready_now else forecast_date.isoformat(),
        "assumption": "Forecast assumes 5 open market days per week, no government/market holiday, and combined planned collection capacity across all symbols.",
        "blockers": blockers,
        "model_forecasts": model_forecasts,
        "next_target": next_target,
        "extra_counts": extra_counts,
    }
