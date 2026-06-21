from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from app.db.session import get_db
from app.config import settings
from app.db.models import OptionChainSnapshot, OptionChainStrike, AnalyticsSnapshot, GeneratedInsight, InsightOutcome
from typing import Dict, Any, List, Optional
import statistics

router = APIRouter()

def calc_diff_pct(curr: float, prev: float) -> float:
    if not prev or prev == 0.0:
        return 0.0
    return ((curr - prev) / prev) * 100

@router.get("/quant-console")
def get_quant_console(
    symbol: str = Query("NIFTY", description="Symbol name (e.g. NIFTY, BANKNIFTY)"),
    expiry: Optional[str] = Query(None, description="Optional expiry date string"),
    date: Optional[str] = Query(None, description="Selected date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Returns structured data for the Quant Validation Console.
    Includes current metrics, comparison with previous snapshot, buildup rule explanations,
    and a chronological timeline of insights.
    """
    from app.api.option_chain import apply_market_hours_filter, get_default_market_date
    if not date:
        date = get_default_market_date(db, symbol)

    if not expiry:
        # Default to the nearest active expiry date at the latest crawled timestamp on that date
        latest_snap_any = db.query(OptionChainSnapshot).filter(
            OptionChainSnapshot.symbol == symbol.upper(),
            OptionChainSnapshot.collection_status == "SUCCESS"
        )
        latest_snap_any = apply_market_hours_filter(latest_snap_any, date)
        latest_snap_any = latest_snap_any.order_by(OptionChainSnapshot.timestamp.desc()).first()
        
        if latest_snap_any:
            # Query all successful expiries at this latest snapshot timestamp
            expiries_at_ts = db.query(OptionChainSnapshot.expiry_date).filter(
                OptionChainSnapshot.symbol == symbol.upper(),
                OptionChainSnapshot.collection_status == "SUCCESS",
                func.datetime(OptionChainSnapshot.timestamp) == func.datetime(latest_snap_any.timestamp)
            ).all()
            
            # Extract and sort expiries
            expiries = [e[0] for e in expiries_at_ts if e[0]]
            
            def parse_date(date_str):
                from datetime import datetime
                try:
                    return datetime.strptime(date_str, "%d-%b-%Y")
                except Exception:
                    return datetime.max
            
            expiries.sort(key=parse_date)
            if expiries:
                expiry = expiries[0]

    # 1. Fetch the latest 2 successful snapshots for this symbol and expiry
    snapshots_query = db.query(OptionChainSnapshot).filter(
        OptionChainSnapshot.symbol == symbol.upper(),
        OptionChainSnapshot.collection_status == "SUCCESS"
    )
    snapshots_query = apply_market_hours_filter(snapshots_query, date)
    if expiry:
        snapshots_query = snapshots_query.filter(OptionChainSnapshot.expiry_date == expiry)
        
    snapshots = snapshots_query.order_by(OptionChainSnapshot.timestamp.desc()).limit(2).all()

    if not snapshots:
        raise HTTPException(
            status_code=404,
            detail=f"No successful snapshots found for symbol {symbol}" +
                   (f" with expiry {expiry}" if expiry else "")
        )

    snap_curr = snapshots[0]
    snap_prev = snapshots[1] if len(snapshots) > 1 else None

    # 2. Get current snapshot metrics
    strikes_curr = db.query(OptionChainStrike).filter(OptionChainStrike.snapshot_id == snap_curr.id).all()
    oi_curr = sum(s.call_oi + s.put_oi for s in strikes_curr)
    vol_curr = sum(s.call_volume + s.put_volume for s in strikes_curr)
    avg_iv_curr = sum(s.call_iv + s.put_iv for s in strikes_curr) / (len(strikes_curr) * 2) if strikes_curr else 0.0

    anal_curr = db.query(AnalyticsSnapshot).filter(AnalyticsSnapshot.source_snapshot_id == snap_curr.id).first()

    current_data = {
        "timestamp": snap_curr.timestamp.isoformat() if snap_curr.timestamp else None,
        "spot_price": snap_curr.spot_price,
        "pcr": anal_curr.pcr if anal_curr else 0.0,
        "average_iv": avg_iv_curr,
        "market_state": anal_curr.market_state if anal_curr else "NEUTRAL",
        "strength": anal_curr.strength if anal_curr else "LOW",
        "total_oi": oi_curr,
        "total_volume": vol_curr
    }

    # 3. Get previous snapshot metrics (if available)
    previous_data = None
    difference_data = {
        "spot_diff_pct": 0.0,
        "pcr_diff_pct": 0.0,
        "iv_diff_pct": 0.0,
        "oi_diff_pct": 0.0,
        "volume_diff_pct": 0.0
    }

    spot_change_pct = 0.0
    oi_change_pct = 0.0
    vol_change_pct = 0.0
    reason_text = "Insufficient historical data to evaluate buildup transitions."

    if snap_prev:
        strikes_prev = db.query(OptionChainStrike).filter(OptionChainStrike.snapshot_id == snap_prev.id).all()
        oi_prev = sum(s.call_oi + s.put_oi for s in strikes_prev)
        vol_prev = sum(s.call_volume + s.put_volume for s in strikes_prev)
        avg_iv_prev = sum(s.call_iv + s.put_iv for s in strikes_prev) / (len(strikes_prev) * 2) if strikes_prev else 0.0

        anal_prev = db.query(AnalyticsSnapshot).filter(AnalyticsSnapshot.source_snapshot_id == snap_prev.id).first()

        previous_data = {
            "timestamp": snap_prev.timestamp.isoformat() if snap_prev.timestamp else None,
            "spot_price": snap_prev.spot_price,
            "pcr": anal_prev.pcr if anal_prev else 0.0,
            "average_iv": avg_iv_prev,
            "market_state": anal_prev.market_state if anal_prev else "NEUTRAL",
            "strength": anal_prev.strength if anal_prev else "LOW",
            "total_oi": oi_prev,
            "total_volume": vol_prev
        }

        # Compute differences
        difference_data["spot_diff_pct"] = calc_diff_pct(snap_curr.spot_price, snap_prev.spot_price)
        difference_data["pcr_diff_pct"] = calc_diff_pct(anal_curr.pcr, anal_prev.pcr) if (anal_curr and anal_prev) else 0.0
        difference_data["iv_diff_pct"] = calc_diff_pct(avg_iv_curr, avg_iv_prev)
        difference_data["oi_diff_pct"] = calc_diff_pct(oi_curr, oi_prev)
        difference_data["volume_diff_pct"] = calc_diff_pct(vol_curr, vol_prev)

        # Buildup rule explanation calculations
        spot_change_pct = difference_data["spot_diff_pct"]
        oi_change_pct = difference_data["oi_diff_pct"]
        vol_change_pct = difference_data["volume_diff_pct"]

        # Formulate reasoning text based on builder rules
        state = anal_curr.market_state if anal_curr else "NEUTRAL"
        strength = anal_curr.strength if anal_curr else "LOW"
        
        # Check time gap safety
        gap_seconds = (snap_curr.timestamp - snap_prev.timestamp).total_seconds()
        if gap_seconds > 1800:
            reason_text = (
                f"Time gap between consecutive snapshots is {gap_seconds/60:.1f} minutes (>30 mins). "
                f"To handle overnight halts/weekends safely, market buildup state was reset to NEUTRAL."
            )
        else:
            direction_price = "upward" if spot_change_pct > 0 else "downward" if spot_change_pct < 0 else "unchanged"
            direction_oi = "addition" if oi_change_pct > 0 else "unwinding" if oi_change_pct < 0 else "unchanged"
            
            reason_text = (
                f"Market state classified as '{state}' ({strength} Strength) because "
                f"Spot price had a {direction_price} move of {spot_change_pct:+.3f}%, and "
                f"Open Interest had a {direction_oi} of {oi_change_pct:+.2f}%. "
                f"Intraday Traded Volume changed by {vol_change_pct:+.2f}%."
            )

    rule_explanation = {
        "spot_change_pct": spot_change_pct,
        "oi_change_pct": oi_change_pct,
        "vol_change_pct": vol_change_pct,
        "reason": reason_text
    }

    # 4. Fetch chronological timeline of latest 15 snapshots
    recent_snaps_query = db.query(OptionChainSnapshot).filter(
        OptionChainSnapshot.symbol == symbol.upper(),
        OptionChainSnapshot.collection_status == "SUCCESS"
    )
    recent_snaps_query = apply_market_hours_filter(recent_snaps_query, date)
    if expiry:
        recent_snaps_query = recent_snaps_query.filter(OptionChainSnapshot.expiry_date == expiry)
    recent_snaps = recent_snaps_query.order_by(OptionChainSnapshot.timestamp.desc()).limit(15).all()

    # Batch-load all analytics + insights for these 15 snapshots to avoid N+1 queries
    recent_snap_ids = [s.id for s in recent_snaps]
    recent_snap_timestamps = [s.timestamp for s in recent_snaps]

    # Batch query: analytics for all 15 snapshots at once
    analytics_list = db.query(AnalyticsSnapshot).filter(
        AnalyticsSnapshot.source_snapshot_id.in_(recent_snap_ids)
    ).all()
    analytics_by_snap_id: Dict[int, AnalyticsSnapshot] = {a.source_snapshot_id: a for a in analytics_list}

    # Batch query: insights for all 15 snapshots at once (by symbol + timestamp + expiry)
    recent_ts_str = [ts.strftime('%Y-%m-%d %H:%M:%S') for ts in recent_snap_timestamps]
    insights_query = db.query(GeneratedInsight).filter(
        GeneratedInsight.symbol == symbol.upper(),
        func.strftime('%Y-%m-%d %H:%M:%S', GeneratedInsight.timestamp).in_(recent_ts_str)
    )
    if expiry:
        insights_query = insights_query.filter(GeneratedInsight.expiry_date == expiry)
    insights_list = insights_query.all()
    # Group insights by timestamp for O(1) lookup
    insights_by_ts: Dict[str, List[str]] = {}
    for ins in insights_list:
        key = ins.timestamp.isoformat() if ins.timestamp else ""
        insights_by_ts.setdefault(key, []).append(ins.insight_text)

    timeline = []
    # Reverse to represent chronological order (oldest to newest)
    for s in reversed(recent_snaps):
        anal = analytics_by_snap_id.get(s.id)
        ts_key = s.timestamp.isoformat() if s.timestamp else ""
        step_insights = insights_by_ts.get(ts_key, [])

        timeline.append({
            "timestamp": s.timestamp.isoformat() if s.timestamp else None,
            "spot_price": s.spot_price,
            "market_state": anal.market_state if anal else "NEUTRAL",
            "strength": anal.strength if anal else "LOW",
            "pcr": anal.pcr if anal else 0.0,
            "insights": step_insights
        })

    # ─── SECTION 5, 6, 7 & 6.5: EVIDENCE ENGINE STATS ───
    completed_outcomes_query = db.query(InsightOutcome).join(OptionChainSnapshot).filter(
        InsightOutcome.symbol == symbol.upper(),
        InsightOutcome.status == "COMPLETED"
    )
    if expiry:
        completed_outcomes_query = completed_outcomes_query.filter(OptionChainSnapshot.expiry_date == expiry)
    completed_outcomes = completed_outcomes_query.all()

    total_completed = len(completed_outcomes)
    min_sample_size = 30
    insufficient_data = total_completed < min_sample_size

    horizons = ["5m", "15m", "30m", "60m"]

    # Section 5: Historical Alignment (Success Rate)
    alignment_stats = {
        "insufficient_data": insufficient_data,
        "total_samples": total_completed,
        "min_sample_size": min_sample_size,
        "bullish": {
            "total": 0,
            "5m": {"success": 0, "rate": 0.0},
            "15m": {"success": 0, "rate": 0.0},
            "30m": {"success": 0, "rate": 0.0},
            "60m": {"success": 0, "rate": 0.0}
        },
        "bearish": {
            "total": 0,
            "5m": {"success": 0, "rate": 0.0},
            "15m": {"success": 0, "rate": 0.0},
            "30m": {"success": 0, "rate": 0.0},
            "60m": {"success": 0, "rate": 0.0}
        }
    }

    # Section 7: Effect Size (Average Movement)
    effect_size_raw = {
        state: {h: {"sum_pts": 0.0, "sum_pct": 0.0, "count": 0} for h in horizons}
        for state in ["LONG BUILD-UP", "SHORT BUILD-UP", "SHORT COVERING", "LONG UNWINDING"]
    }

    # Section 6.5: State vs Outcome Matrix (UP, FLAT, DOWN percentages at 60m)
    state_outcome_matrix_raw = {
        state: {"up": 0, "flat": 0, "down": 0, "total": 0}
        for state in ["LONG BUILD-UP", "SHORT BUILD-UP", "SHORT COVERING", "LONG UNWINDING"]
    }

    thresh_pts = settings.OUTCOME_SUCCESS_THRESHOLD_POINTS

    for out in completed_outcomes:
        is_bullish = out.prediction_direction == "BULLISH"
        is_bearish = out.prediction_direction == "BEARISH"

        if is_bullish:
            alignment_stats["bullish"]["total"] += 1
        elif is_bearish:
            alignment_stats["bearish"]["total"] += 1

        # Evaluate 5m
        if out.spot_after_5m is not None:
            pts = out.movement_5m_points or 0.0
            pct = out.movement_5m_pct or 0.0
            if out.market_state in effect_size_raw:
                effect_size_raw[out.market_state]["5m"]["sum_pts"] += pts
                effect_size_raw[out.market_state]["5m"]["sum_pct"] += pct
                effect_size_raw[out.market_state]["5m"]["count"] += 1
            if is_bullish and pts >= thresh_pts:
                alignment_stats["bullish"]["5m"]["success"] += 1
            elif is_bearish and pts <= -thresh_pts:
                alignment_stats["bearish"]["5m"]["success"] += 1

        # Evaluate 15m
        if out.spot_after_15m is not None:
            pts = out.movement_15m_points or 0.0
            pct = out.movement_15m_pct or 0.0
            if out.market_state in effect_size_raw:
                effect_size_raw[out.market_state]["15m"]["sum_pts"] += pts
                effect_size_raw[out.market_state]["15m"]["sum_pct"] += pct
                effect_size_raw[out.market_state]["15m"]["count"] += 1
            if is_bullish and pts >= thresh_pts:
                alignment_stats["bullish"]["15m"]["success"] += 1
            elif is_bearish and pts <= -thresh_pts:
                alignment_stats["bearish"]["15m"]["success"] += 1

        # Evaluate 30m
        if out.spot_after_30m is not None:
            pts = out.movement_30m_points or 0.0
            pct = out.movement_30m_pct or 0.0
            if out.market_state in effect_size_raw:
                effect_size_raw[out.market_state]["30m"]["sum_pts"] += pts
                effect_size_raw[out.market_state]["30m"]["sum_pct"] += pct
                effect_size_raw[out.market_state]["30m"]["count"] += 1
            if is_bullish and pts >= thresh_pts:
                alignment_stats["bullish"]["30m"]["success"] += 1
            elif is_bearish and pts <= -thresh_pts:
                alignment_stats["bearish"]["30m"]["success"] += 1

        # Evaluate 60m & Outcomes Matrix
        if out.spot_after_60m is not None:
            pts = out.movement_60m_points or 0.0
            pct = out.movement_60m_pct or 0.0
            if out.market_state in effect_size_raw:
                effect_size_raw[out.market_state]["60m"]["sum_pts"] += pts
                effect_size_raw[out.market_state]["60m"]["sum_pct"] += pct
                effect_size_raw[out.market_state]["60m"]["count"] += 1
            if is_bullish and pts >= thresh_pts:
                alignment_stats["bullish"]["60m"]["success"] += 1
            elif is_bearish and pts <= -thresh_pts:
                alignment_stats["bearish"]["60m"]["success"] += 1

            # State vs Outcome matrix counts
            if out.market_state in state_outcome_matrix_raw:
                state_outcome_matrix_raw[out.market_state]["total"] += 1
                if pts >= thresh_pts:
                    state_outcome_matrix_raw[out.market_state]["up"] += 1
                elif pts <= -thresh_pts:
                    state_outcome_matrix_raw[out.market_state]["down"] += 1
                else:
                    state_outcome_matrix_raw[out.market_state]["flat"] += 1

    # Format Section 5 alignment rates
    for side in ["bullish", "bearish"]:
        total = alignment_stats[side]["total"]
        for h in horizons:
            success = alignment_stats[side][h]["success"]
            alignment_stats[side][h]["rate"] = (success / total) * 100 if total > 0 else 0.0

    # Format Section 7 Effect Sizes
    effect_size = {}
    for state, h_data in effect_size_raw.items():
        effect_size[state] = {}
        for h in horizons:
            count = h_data[h]["count"]
            avg_pts = h_data[h]["sum_pts"] / count if count > 0 else 0.0
            avg_pct = h_data[h]["sum_pct"] / count if count > 0 else 0.0
            effect_size[state][h] = {
                "avg_points": avg_pts,
                "avg_pct": avg_pct,
                "samples": count
            }

    # Format Section 6.5 Outcomes Matrix
    state_outcome_matrix = {}
    for state, counts in state_outcome_matrix_raw.items():
        total = counts["total"]
        state_outcome_matrix[state] = {
            "up_pct": (counts["up"] / total) * 100 if total > 0 else 0.0,
            "flat_pct": (counts["flat"] / total) * 100 if total > 0 else 0.0,
            "down_pct": (counts["down"] / total) * 100 if total > 0 else 0.0,
            "total_samples": total
        }

    # Section 6: State Occurrence Distribution (computed from all successful historical snapshots)
    all_analytics = db.query(AnalyticsSnapshot).filter(
        AnalyticsSnapshot.symbol == symbol.upper()
    ).all()
    total_snapshots = len(all_analytics)
    state_counts = {
        "LONG BUILD-UP": 0,
        "SHORT BUILD-UP": 0,
        "SHORT COVERING": 0,
        "LONG UNWINDING": 0,
        "NEUTRAL": 0
    }
    for anal in all_analytics:
        if anal.market_state in state_counts:
            state_counts[anal.market_state] += 1

    state_distribution = {}
    for state, count in state_counts.items():
        state_distribution[state] = {
            "count": count,
            "percentage": (count / total_snapshots) * 100 if total_snapshots > 0 else 0.0
        }

    # ─── SECTION 8: EXCURSION ANALYSIS (MFE / MAE) ───
    states_list = ["LONG BUILD-UP", "SHORT BUILD-UP", "SHORT COVERING", "LONG UNWINDING"]
    excursion_groups = {state: [] for state in states_list}

    for out in completed_outcomes:
        if out.market_state in excursion_groups and out.max_favorable_move_60m is not None:
            excursion_groups[out.market_state].append(out)

    excursion_analysis = {}
    is_mock_data = False

    for state in states_list:
        outcomes_in_state = excursion_groups[state]
        count = len(outcomes_in_state)

        if count > 0:
            mfes_pts = [o.max_favorable_move_60m for o in outcomes_in_state]
            maes_pts = [o.max_adverse_move_60m for o in outcomes_in_state]

            mfes_pct = [(o.max_favorable_move_60m / o.spot_at_generation) * 100 for o in outcomes_in_state]
            maes_pct = [(o.max_adverse_move_60m / o.spot_at_generation) * 100 for o in outcomes_in_state]

            times_mfe = [o.time_to_mfe_minutes for o in outcomes_in_state if o.time_to_mfe_minutes is not None]
            times_mae = [o.time_to_mae_minutes for o in outcomes_in_state if o.time_to_mae_minutes is not None]

            if any(o.is_mock for o in outcomes_in_state):
                is_mock_data = True

            avg_mfe_pts = sum(mfes_pts) / count
            avg_mfe_pct = sum(mfes_pct) / count
            avg_mae_pts = sum(maes_pts) / count
            avg_mae_pct = sum(maes_pct) / count

            excursion_analysis[state] = {
                "avg_mfe_points": avg_mfe_pts,
                "avg_mfe_pct": avg_mfe_pct,
                "avg_mae_points": avg_mae_pts,
                "avg_mae_pct": avg_mae_pct,

                "median_mfe_points": statistics.median(mfes_pts),
                "median_mfe_pct": statistics.median(mfes_pct),
                "median_mae_points": statistics.median(maes_pts),
                "median_mae_pct": statistics.median(maes_pct),

                "best_mfe_points": max(mfes_pts),
                "best_mfe_pct": max(mfes_pct),
                "worst_mae_points": min(maes_pts),
                "worst_mae_pct": min(maes_pct),

                "avg_time_to_mfe": sum(times_mfe) / len(times_mfe) if times_mfe else 0.0,
                "avg_time_to_mae": sum(times_mae) / len(times_mae) if times_mae else 0.0,

                "expectancy_points": avg_mfe_pts + avg_mae_pts,
                "expectancy_pct": avg_mfe_pct + avg_mae_pct,
                "total_samples": count
            }
        else:
            excursion_analysis[state] = {
                "avg_mfe_points": 0.0, "avg_mfe_pct": 0.0,
                "avg_mae_points": 0.0, "avg_mae_pct": 0.0,
                "median_mfe_points": 0.0, "median_mfe_pct": 0.0,
                "median_mae_points": 0.0, "median_mae_pct": 0.0,
                "best_mfe_points": 0.0, "best_mfe_pct": 0.0,
                "worst_mae_points": 0.0, "worst_mae_pct": 0.0,
                "avg_time_to_mfe": 0.0, "avg_time_to_mae": 0.0,
                "expectancy_points": 0.0, "expectancy_pct": 0.0,
                "total_samples": 0
            }

    if any(o.is_mock for o in completed_outcomes):
        is_mock_data = True

    return {
        "symbol": symbol.upper(),
        "current": current_data,
        "previous": previous_data,
        "difference": difference_data,
        "rule_explanation": rule_explanation,
        "timeline": timeline,
        "evidence_engine": alignment_stats,
        "state_distribution": state_distribution,
        "effect_size": effect_size,
        "state_outcome_matrix": state_outcome_matrix,
        "excursion_analysis": excursion_analysis,
        "is_mock_data": is_mock_data
    }

@router.get("/historical-trends")
def get_historical_trends(
    symbol: str = Query("NIFTY", description="Symbol name (e.g. NIFTY, BANKNIFTY)"),
    expiry: Optional[str] = Query(None, description="Optional expiry date string"),
    date: Optional[str] = Query(None, description="Selected date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Returns historical data series for PCR, IV, call/put OI, and S/R levels
    for the last 50 snapshots of a symbol/expiry.
    """
    from sqlalchemy import func
    from app.api.option_chain import apply_market_hours_filter, get_default_market_date
    
    if not date:
        date = get_default_market_date(db, symbol)

    if not expiry:
        # Default to the nearest active expiry date at the latest crawled snapshot on that date
        latest_snap_any = db.query(OptionChainSnapshot).filter(
            OptionChainSnapshot.symbol == symbol.upper(),
            OptionChainSnapshot.collection_status == "SUCCESS"
        )
        latest_snap_any = apply_market_hours_filter(latest_snap_any, date)
        latest_snap_any = latest_snap_any.order_by(OptionChainSnapshot.timestamp.desc()).first()
        
        if latest_snap_any:
            # Query all successful expiries at this latest snapshot timestamp
            expiries_at_ts = db.query(OptionChainSnapshot.expiry_date).filter(
                OptionChainSnapshot.symbol == symbol.upper(),
                OptionChainSnapshot.collection_status == "SUCCESS",
                OptionChainSnapshot.timestamp == latest_snap_any.timestamp
            ).all()
            
            expiries = [e[0] for e in expiries_at_ts if e[0]]
            
            def parse_date(date_str):
                from datetime import datetime
                try:
                    return datetime.strptime(date_str, "%d-%b-%Y")
                except Exception:
                    return datetime.max
            
            expiries.sort(key=parse_date)
            if expiries:
                expiry = expiries[0]

    # Query the latest 50 successful snapshots
    snapshots_query = db.query(OptionChainSnapshot).filter(
        OptionChainSnapshot.symbol == symbol.upper(),
        OptionChainSnapshot.expiry_date == expiry,
        OptionChainSnapshot.collection_status == "SUCCESS"
    )
    snapshots_query = apply_market_hours_filter(snapshots_query, date)
    snapshots = snapshots_query.order_by(OptionChainSnapshot.timestamp.desc()).limit(50).all()
    
    # Reverse to keep chronological order
    snapshots.reverse()
    
    if not snapshots:
        return {
            "symbol": symbol.upper(),
            "expiry_date": expiry,
            "trends": []
        }
        
    snap_ids = [s.id for s in snapshots]
    
    # Batch query analytics
    analytics_list = db.query(AnalyticsSnapshot).filter(
        AnalyticsSnapshot.source_snapshot_id.in_(snap_ids)
    ).all()
    analytics_map = {a.source_snapshot_id: a for a in analytics_list}
    
    # Batch query strike stats (Call/Put OI and average IV)
    strike_stats = db.query(
        OptionChainStrike.snapshot_id,
        func.sum(OptionChainStrike.call_oi).label("total_call_oi"),
        func.sum(OptionChainStrike.put_oi).label("total_put_oi"),
        func.sum(OptionChainStrike.call_iv + OptionChainStrike.put_iv).label("sum_iv"),
        func.count(OptionChainStrike.id).label("strike_count")
    ).filter(OptionChainStrike.snapshot_id.in_(snap_ids)).group_by(OptionChainStrike.snapshot_id).all()
    
    stats_map = {
        s.snapshot_id: {
            "total_call_oi": s.total_call_oi,
            "total_put_oi": s.total_put_oi,
            "avg_iv": (s.sum_iv / (s.strike_count * 2)) if s.strike_count > 0 else 0.0
        }
        for s in strike_stats
    }
    
    trend_data = []
    for s in snapshots:
        anal = analytics_map.get(s.id)
        stats = stats_map.get(s.id, {"total_call_oi": 0, "total_put_oi": 0, "avg_iv": 0.0})
        
        trend_data.append({
            "timestamp": s.timestamp.isoformat() if s.timestamp else None,
            "spot_price": s.spot_price,
            "pcr": anal.pcr if anal else 0.0,
            "average_iv": stats["avg_iv"],
            "total_call_oi": stats["total_call_oi"],
            "total_put_oi": stats["total_put_oi"],
            "support": anal.support if anal else None,
            "secondary_support": anal.secondary_support if anal else None,
            "resistance": anal.resistance if anal else None,
            "secondary_resistance": anal.secondary_resistance if anal else None,
        })
        
    return {
        "symbol": symbol.upper(),
        "expiry_date": expiry,
        "trends": trend_data
    }



@router.get("/quant/benchmark-sr")
def benchmark_support_resistance(
    symbol: str = Query("NIFTY", description="Symbol name (e.g. NIFTY, BANKNIFTY)"),
    limit: int = Query(200, description="Max snapshots to evaluate (to keep execution fast)", ge=10, le=1000),
    db: Session = Depends(get_db)
):
    """
    Benchmarks Classic S/R (OI only) vs Weighted S/R (OI + ChangeOI) on historical data.
    Calculates Hold Rate (did it breach in 60m?) and Touch Proximity (how close did the price get when held).
    """
    symbol = symbol.upper()
    
    # 1. Fetch successful snapshots sorted chronologically
    snapshots = db.query(OptionChainSnapshot).filter(
        OptionChainSnapshot.symbol == symbol,
        OptionChainSnapshot.collection_status == "SUCCESS"
    ).order_by(OptionChainSnapshot.timestamp.asc()).all()
    
    if len(snapshots) < 10:
        return {
            "status": "INSUFFICIENT_DATA",
            "message": f"Found only {len(snapshots)} snapshots, need at least 10 to benchmark."
        }
        
    # Map snapshot IDs to strikes
    snap_ids = [s.id for s in snapshots]
    strikes = db.query(OptionChainStrike).filter(
        OptionChainStrike.snapshot_id.in_(snap_ids)
    ).all()
    
    # Group strikes by snapshot_id
    strikes_by_snap = {}
    for st in strikes:
        if st.snapshot_id not in strikes_by_snap:
            strikes_by_snap[st.snapshot_id] = []
        strikes_by_snap[st.snapshot_id].append(st)
        
    # Spot price grid
    spot_grid = [(s.timestamp, s.spot_price) for s in snapshots]
    
    # Weights from settings
    oi_w = settings.OI_WEIGHT
    coi_w = settings.CHANGE_OI_WEIGHT
    
    classic_support_held = 0
    classic_resistance_held = 0
    weighted_support_held = 0
    weighted_resistance_held = 0
    
    classic_support_prox = []
    classic_resistance_prox = []
    weighted_support_prox = []
    weighted_resistance_prox = []
    
    evaluated_samples = 0
    
    # We will sample from the snapshots (using stride or limit from the end to cover recent history)
    # If we have more than the limit, we evaluate the last 'limit' snapshots that have 60m of subsequent data.
    candidate_indices = []
    for i, s in enumerate(snapshots):
        t0 = s.timestamp
        # Check if we have subsequent data for at least 50 minutes on the same day
        t_max_target = t0 + timedelta(minutes=50)
        has_subsequent = False
        for j in range(i + 1, len(snapshots)):
            if snapshots[j].timestamp >= t_max_target and snapshots[j].timestamp.date() == t0.date():
                has_subsequent = True
                break
        if has_subsequent:
            candidate_indices.append(i)
            
    # Limit candidates to the most recent ones
    if len(candidate_indices) > limit:
        candidate_indices = candidate_indices[-limit:]
        
    for idx in candidate_indices:
        s = snapshots[idx]
        t0 = s.timestamp
        s0 = s.spot_price
        snap_strikes = strikes_by_snap.get(s.id, [])
        if not snap_strikes:
            continue
            
        # 1. Calculate Classic S/R (OI only: change weight is 0.0)
        sorted_puts_classic = sorted(snap_strikes, key=lambda st: st.put_oi, reverse=True)
        classic_support = sorted_puts_classic[0].strike if sorted_puts_classic else s0
        
        sorted_calls_classic = sorted(snap_strikes, key=lambda st: st.call_oi, reverse=True)
        classic_resistance = sorted_calls_classic[0].strike if sorted_calls_classic else s0
        
        # 2. Calculate Weighted S/R (using config weights)
        sorted_puts_weighted = sorted(snap_strikes, key=lambda st: (st.put_oi * oi_w) + (st.put_change_oi * coi_w), reverse=True)
        weighted_support = sorted_puts_weighted[0].strike if sorted_puts_weighted else s0
        
        sorted_calls_weighted = sorted(snap_strikes, key=lambda st: (st.call_oi * oi_w) + (st.call_change_oi * coi_w), reverse=True)
        weighted_resistance = sorted_calls_weighted[0].strike if sorted_calls_weighted else s0
        
        # 3. Find price range in the next 60m window (same day)
        t_end = t0 + timedelta(minutes=60)
        future_spots = [g[1] for g in spot_grid if t0 <= g[0] <= t_end and g[0].date() == t0.date()]
        
        if not future_spots:
            continue
            
        p_min = min(future_spots)
        p_max = max(future_spots)
        
        # 4. Evaluate Classic S/R
        # Support
        c_support_ok = p_min >= classic_support
        if c_support_ok:
            classic_support_held += 1
            classic_support_prox.append(p_min - classic_support)
            
        # Resistance
        c_resistance_ok = p_max <= classic_resistance
        if c_resistance_ok:
            classic_resistance_held += 1
            classic_resistance_prox.append(classic_resistance - p_max)
            
        # 5. Evaluate Weighted S/R
        # Support
        w_support_ok = p_min >= weighted_support
        if w_support_ok:
            weighted_support_held += 1
            weighted_support_prox.append(p_min - weighted_support)
            
        # Resistance
        w_resistance_ok = p_max <= weighted_resistance
        if w_resistance_ok:
            weighted_resistance_held += 1
            weighted_resistance_prox.append(weighted_resistance - p_max)
            
        evaluated_samples += 1
        
    if evaluated_samples == 0:
        return {
            "status": "INSUFFICIENT_DATA",
            "message": "No snapshots had a full 60-minute window of subsequent historical data on the same day."
        }
        
    # Calculate stats
    c_sup_rate = (classic_support_held / evaluated_samples) * 100.0
    c_res_rate = (classic_resistance_held / evaluated_samples) * 100.0
    c_comb_rate = (c_sup_rate + c_res_rate) / 2.0
    
    w_sup_rate = (weighted_support_held / evaluated_samples) * 100.0
    w_res_rate = (weighted_resistance_held / evaluated_samples) * 100.0
    w_comb_rate = (w_sup_rate + w_res_rate) / 2.0
    
    c_sup_prox_avg = sum(classic_support_prox) / len(classic_support_prox) if classic_support_prox else 0.0
    c_res_prox_avg = sum(classic_resistance_prox) / len(classic_resistance_prox) if classic_resistance_prox else 0.0
    w_sup_prox_avg = sum(weighted_support_prox) / len(weighted_support_prox) if weighted_support_prox else 0.0
    w_res_prox_avg = sum(weighted_resistance_prox) / len(weighted_resistance_prox) if weighted_resistance_prox else 0.0
    
    return {
        "status": "SUCCESS",
        "symbol": symbol,
        "evaluated_samples": evaluated_samples,
        "classic": {
            "support_hold_rate": round(c_sup_rate, 1),
            "resistance_hold_rate": round(c_res_rate, 1),
            "combined_hold_rate": round(c_comb_rate, 1),
            "support_touch_proximity": round(c_sup_prox_avg, 1),
            "resistance_touch_proximity": round(c_res_prox_avg, 1)
        },
        "weighted": {
            "support_hold_rate": round(w_sup_rate, 1),
            "resistance_hold_rate": round(w_res_rate, 1),
            "combined_hold_rate": round(w_comb_rate, 1),
            "support_touch_proximity": round(w_sup_prox_avg, 1),
            "resistance_touch_proximity": round(w_res_prox_avg, 1)
        },
        "interpretation": (
            "Weighted S/R holds better than Classic S/R."
            if w_comb_rate > c_comb_rate else
            "Classic S/R holds better than or equal to Weighted S/R."
        )
    }


