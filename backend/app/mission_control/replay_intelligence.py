from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import OptionChainSnapshot, PremiumEvolution, TradingSignal


MARKET_OPEN_UTC_HOUR = 3
MARKET_OPEN_UTC_MINUTE = 45
MARKET_CLOSE_UTC_HOUR = 10
MARKET_CLOSE_UTC_MINUTE = 0


def _session_bounds(market_date: str) -> tuple[datetime, datetime]:
    parsed = datetime.strptime(market_date, "%Y-%m-%d")
    return (
        parsed.replace(hour=MARKET_OPEN_UTC_HOUR, minute=MARKET_OPEN_UTC_MINUTE, second=0, microsecond=0),
        parsed.replace(hour=MARKET_CLOSE_UTC_HOUR, minute=MARKET_CLOSE_UTC_MINUTE, second=0, microsecond=0),
    )


def get_replay_intelligence(db: Session, symbol: str | None = None) -> dict:
    query = db.query(OptionChainSnapshot).filter(OptionChainSnapshot.collection_status == "SUCCESS")
    if symbol:
        query = query.filter(OptionChainSnapshot.symbol == symbol.upper())

    day_rows = query.with_entities(func.date(OptionChainSnapshot.timestamp), func.count(OptionChainSnapshot.id)).group_by(
        func.date(OptionChainSnapshot.timestamp)
    ).all()
    replay_days = []
    full_days = 0
    partial_days = 0
    for date_value, count in day_rows:
        expected_snapshots = 376
        coverage_pct = round(min(100.0, (count / expected_snapshots) * 100.0), 2)
        if coverage_pct >= 85:
            full_days += 1
        elif count:
            partial_days += 1
        replay_days.append({
            "market_date": str(date_value),
            "snapshots": count,
            "coverage_pct": coverage_pct,
            "status": "FULL" if coverage_pct >= 85 else "PARTIAL",
        })

    replay_days.sort(key=lambda item: item["market_date"], reverse=True)
    total_days = len(replay_days)
    average_coverage = round(sum(day["coverage_pct"] for day in replay_days) / total_days, 2) if total_days else 0.0

    signal_query = db.query(TradingSignal)
    if symbol:
        signal_query = signal_query.filter(TradingSignal.symbol == symbol.upper())
    signal_count = signal_query.count()
    premium_paths = db.query(PremiumEvolution).count()
    hindsight_coverage_pct = round((premium_paths / signal_count * 100.0), 2) if signal_count else 0.0

    return {
        "engine": "Market Replay Engine",
        "status": "READY" if full_days else ("DEGRADED" if partial_days else "BLOCKED"),
        "total_replay_days": total_days,
        "full_replay_days": full_days,
        "partial_replay_days": partial_days,
        "average_session_coverage_pct": average_coverage,
        "hindsight_coverage_pct": hindsight_coverage_pct,
        "latest_sessions": replay_days[:10],
        "capabilities": {
            "market_evolution": True,
            "signal_timeline": True,
            "confidence_timeline": True,
            "premium_evolution": premium_paths > 0,
            "hindsight_outcomes": hindsight_coverage_pct > 0,
            "leakage_safe_time_travel": True,
        },
        "session_contract": {
            "market_open_ist": "09:15",
            "market_close_ist": "15:30",
            "stored_timestamp": "naive UTC",
        },
    }


def get_replay_session_contract(market_date: str) -> dict:
    start, end = _session_bounds(market_date)
    return {
        "market_date": market_date,
        "start_utc": start.isoformat(),
        "end_utc": end.isoformat(),
        "start_ist": "09:15",
        "end_ist": "15:30",
        "future_leakage_rule": "Each replay step may only use data available at or before that timestamp.",
    }

