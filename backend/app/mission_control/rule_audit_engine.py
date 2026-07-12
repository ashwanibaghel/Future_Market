from __future__ import annotations

import json
import math
from collections import Counter, defaultdict

from sqlalchemy.orm import Session

from app.db.models import TradingSignal


def _safe_json(value: str | None) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _pearson(left: list[float], right: list[float]) -> float:
    if len(left) < 3 or len(left) != len(right):
        return 0.0
    mean_left = sum(left) / len(left)
    mean_right = sum(right) / len(right)
    numerator = sum((x - mean_left) * (y - mean_right) for x, y in zip(left, right))
    denom_left = math.sqrt(sum((x - mean_left) ** 2 for x in left))
    denom_right = math.sqrt(sum((y - mean_right) ** 2 for y in right))
    if denom_left == 0 or denom_right == 0:
        return 0.0
    return round(numerator / (denom_left * denom_right), 4)


def get_rule_audit(db: Session, symbol: str | None = None, version: str | None = None) -> dict:
    query = db.query(TradingSignal)
    if symbol:
        query = query.filter(TradingSignal.symbol == symbol.upper())
    if version:
        query = query.filter(TradingSignal.signal_version == version)
    signals = query.order_by(TradingSignal.timestamp.desc()).limit(1000).all()

    rule_usage = Counter()
    rule_contribution_sum = defaultdict(float)
    rule_series = defaultdict(list)
    rejection_reasons = Counter()
    confidence_values = []
    resolved = wins = losses = flats = 0
    active_signals = 0

    for signal in signals:
        if signal.signal_type in ("BUY_CALL", "BUY_PUT"):
            active_signals += 1
        if signal.confidence_ratio is not None:
            confidence_values.append(float(signal.confidence_ratio))
        if signal.signal_type == "NO_TRADE" and signal.closest_failed_rule:
            rejection_reasons[signal.closest_failed_rule] += 1

        reasons = _safe_json(signal.reasons)
        for rule_name, payload in reasons.items():
            contribution = 0.0
            if isinstance(payload, dict):
                contribution = float(payload.get("contribution") or 0.0)
            elif isinstance(payload, bool):
                contribution = 1.0 if payload else 0.0
            rule_usage[rule_name] += 1
            rule_contribution_sum[rule_name] += contribution
            rule_series[rule_name].append(contribution)

        outcome = signal.outcome_60m if signal.outcome_60m != "PENDING" else (
            signal.outcome_30m if signal.outcome_30m != "PENDING" else signal.outcome_15m
        )
        if outcome in ("WIN", "LOSS", "FLAT"):
            resolved += 1
            if outcome == "WIN":
                wins += 1
            elif outcome == "LOSS":
                losses += 1
            else:
                flats += 1

    total = len(signals)
    rule_contributions = []
    for rule_name, count in rule_usage.most_common():
        rule_contributions.append({
            "rule": rule_name,
            "usage_count": count,
            "coverage_pct": round((count / total * 100.0), 2) if total else 0.0,
            "average_contribution": round(rule_contribution_sum[rule_name] / count, 4) if count else 0.0,
            "status": "CORE" if total and count / total >= 0.15 else "SUPPORTING",
        })

    correlation_pairs = []
    rule_names = list(rule_series.keys())
    for index, left_name in enumerate(rule_names):
        for right_name in rule_names[index + 1:]:
            left = rule_series[left_name]
            right = rule_series[right_name]
            sample_size = min(len(left), len(right))
            correlation_pairs.append({
                "left": left_name,
                "right": right_name,
                "correlation": _pearson(left[:sample_size], right[:sample_size]),
                "sample_size": sample_size,
            })
    correlation_pairs.sort(key=lambda item: abs(item["correlation"]), reverse=True)

    decisive = wins + losses
    accuracy = round((wins / decisive * 100.0), 2) if decisive else 0.0
    avg_confidence = round(sum(confidence_values) / len(confidence_values), 2) if confidence_values else 0.0

    return {
        "engine": "Quant Research Assistant",
        "status": "READY" if total >= 100 else ("DEGRADED" if total else "BLOCKED"),
        "total_signals_audited": total,
        "active_signals": active_signals,
        "resolved_signals": resolved,
        "wins": wins,
        "losses": losses,
        "flats": flats,
        "accuracy_pct": accuracy,
        "average_confidence": avg_confidence,
        "rule_contributions": rule_contributions[:20],
        "rejection_reasons": [
            {"reason": reason, "count": count, "coverage_pct": round(count / max(1, total) * 100.0, 2)}
            for reason, count in rejection_reasons.most_common(10)
        ],
        "correlations": correlation_pairs[:20],
        "signal_quality": {
            "resolved_pct": round((resolved / total * 100.0), 2) if total else 0.0,
            "active_signal_pct": round((active_signals / total * 100.0), 2) if total else 0.0,
            "calibration_gap": round(abs(avg_confidence - accuracy), 2) if decisive else 0.0,
        },
    }

