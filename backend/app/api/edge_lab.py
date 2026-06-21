from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import (
    OptionChainSnapshot, AnalyticsSnapshot, InsightOutcome,
    OptionChainSnapshot5m, AnalyticsSnapshot5m,
    OptionChainSnapshot15m, AnalyticsSnapshot15m
)
from typing import Dict, Any, List, Optional
import math
import statistics
from datetime import timedelta

router = APIRouter()

def get_prediction_direction(market_state: str) -> str:
    if market_state in ["LONG BUILD-UP", "SHORT COVERING"]:
        return "BULLISH"
    elif market_state in ["SHORT BUILD-UP", "LONG UNWINDING"]:
        return "BEARISH"
    return "NEUTRAL"

def calculate_metrics_for_group(outcomes: List[Dict[str, Any]], market_state: str) -> Dict[str, Any]:
    samples = len(outcomes)
    if samples < 20:
        return {
            "market_state": market_state,
            "samples": samples,
            "status": "INSUFFICIENT_DATA"
        }

    direction = get_prediction_direction(market_state)
    
    # 1. Success Rates
    success_15m_count = 0
    success_30m_count = 0
    success_60m_count = 0
    
    mfe_list = []
    mae_list = []
    move_60m_list = []
    
    for o in outcomes:
        m15 = o.get("movement_15m_points")
        m30 = o.get("movement_30m_points")
        m60 = o.get("movement_60m_points")
        mfe = o.get("max_favorable_move_60m")
        mae = o.get("max_adverse_move_60m")
        
        if direction == "BULLISH":
            if m15 is not None and m15 > 0: success_15m_count += 1
            if m30 is not None and m30 > 0: success_30m_count += 1
            if m60 is not None and m60 > 0: success_60m_count += 1
        else: # BEARISH
            if m15 is not None and m15 < 0: success_15m_count += 1
            if m30 is not None and m30 < 0: success_30m_count += 1
            if m60 is not None and m60 < 0: success_60m_count += 1
            
        if mfe is not None: mfe_list.append(mfe)
        if mae is not None: mae_list.append(mae)
        if m60 is not None: move_60m_list.append(m60)

    success_15m = (success_15m_count / samples) * 100.0
    success_30m = (success_30m_count / samples) * 100.0
    success_60m = (success_60m_count / samples) * 100.0
    
    # 2. Excursions (Averages and Medians)
    avg_mfe = sum(mfe_list) / len(mfe_list) if mfe_list else 0.0
    avg_mae = sum(mae_list) / len(mae_list) if mae_list else 0.0
    
    median_mfe = statistics.median(mfe_list) if mfe_list else 0.0
    median_mae = statistics.median(mae_list) if mae_list else 0.0
    
    # 3. Edge Score: (Success Rate 60m * 0.6) + (Excursion Ratio Score * 0.4)
    # Excursion Ratio Score = min(100.0, (avg_mfe / max(1.0, abs(avg_mae))) * 20.0)
    excursion_ratio = avg_mfe / max(1.0, abs(avg_mae))
    excursion_score = min(100.0, excursion_ratio * 20.0)
    edge_score = (success_60m * 0.6) + (excursion_score * 0.4)
    
    # 4. Confidence Tiers
    if samples < 20:
        confidence = "INSUFFICIENT DATA"
        confidence_val = 0
    elif samples <= 50:
        confidence = "LOW"
        confidence_val = 40
    elif samples <= 100:
        confidence = "MEDIUM"
        confidence_val = 70
    else:
        confidence = "HIGH"
        confidence_val = 100
        
    # 5. Stability Score & movement_std_dev
    # CV = std_dev / avg_move
    # Consistency Score = 100 / (1 + CV)
    if len(move_60m_list) >= 2:
        movement_std_dev = statistics.stdev(move_60m_list)
        # Average of absolute movements to prevent signs cancellation
        avg_move = sum(abs(x) for x in move_60m_list) / len(move_60m_list)
        cv = movement_std_dev / max(1.0, avg_move)
        consistency_score = 100.0 / (1.0 + cv)
    else:
        movement_std_dev = 0.0
        consistency_score = 100.0
        
    # 6. Edge Decay
    edge_decay = success_60m - success_15m
    
    # 7. Edge Quality (Composite Score)
    composite_score = (edge_score * 0.4) + (consistency_score * 0.4) + (confidence_val * 0.2)
    if composite_score >= 75:
        edge_quality = "HIGH QUALITY"
    elif composite_score >= 50:
        edge_quality = "MEDIUM QUALITY"
    else:
        edge_quality = "LOW QUALITY"
        
    return {
        "market_state": market_state,
        "samples": samples,
        "success_15m": round(success_15m, 1),
        "success_30m": round(success_30m, 1),
        "success_60m": round(success_60m, 1),
        "avg_mfe": round(avg_mfe, 1),
        "median_mfe": round(median_mfe, 1),
        "avg_mae": round(avg_mae, 1),
        "median_mae": round(median_mae, 1),
        "edge_score": round(edge_score, 1),
        "confidence": confidence,
        "edge_decay": round(edge_decay, 1),
        "movement_std_dev": round(movement_std_dev, 1),
        "consistency_score": round(consistency_score, 1),
        "edge_quality": edge_quality,
        "status": "SUCCESS"
    }

def find_closest_spot(timestamp, snapshots_list, tolerance_minutes=5):
    # Binary search or scan
    best_snap = None
    min_diff = timedelta(minutes=tolerance_minutes)
    
    for snap_ts, spot in snapshots_list:
        diff = abs(snap_ts - timestamp)
        if diff < min_diff:
            min_diff = diff
            best_snap = spot
            
    return best_snap

@router.get("/edge-lab")
def get_edge_lab_metrics(
    symbol: str = Query("NIFTY", description="Symbol name (e.g. NIFTY, BANKNIFTY)"),
    timeframe: str = Query("1m", description="Timeframe aggregation (1m, 5m, 15m)"),
    db: Session = Depends(get_db)
):
    symbol = symbol.upper()
    
    # Clean timeframe query parameter
    tf_clean = timeframe.lower().strip()
    if "minute" in tf_clean:
        if "1" in tf_clean:
            tf_clean = "1m"
        elif "5" in tf_clean:
            tf_clean = "5m"
        elif "15" in tf_clean:
            tf_clean = "15m"
            
    if tf_clean not in ["1m", "5m", "15m"]:
        tf_clean = "1m"
        
    states = ["LONG BUILD-UP", "SHORT BUILD-UP", "SHORT COVERING", "LONG UNWINDING"]
    grouped_outcomes = {s: [] for s in states}
    
    if tf_clean == "1m":
        # Query completed outcomes from DB (strictly real data: is_mock == False)
        real_db_outcomes = db.query(InsightOutcome).filter(
            InsightOutcome.symbol == symbol,
            InsightOutcome.is_mock == False,
            InsightOutcome.status == "COMPLETED"
        ).all()
        
        for o in real_db_outcomes:
            if o.market_state in grouped_outcomes:
                grouped_outcomes[o.market_state].append({
                    "movement_15m_points": o.movement_15m_points,
                    "movement_30m_points": o.movement_30m_points,
                    "movement_60m_points": o.movement_60m_points,
                    "max_favorable_move_60m": o.max_favorable_move_60m,
                    "max_adverse_move_60m": o.max_adverse_move_60m
                })
    else:
        # 5m or 15m dynamic computation from historical data (strictly real data)
        if tf_clean == "5m":
            snap_cls = OptionChainSnapshot5m
            anal_cls = AnalyticsSnapshot5m
        else:
            snap_cls = OptionChainSnapshot15m
            anal_cls = AnalyticsSnapshot15m
            
        snaps = db.query(snap_cls).filter(
            snap_cls.symbol == symbol,
            snap_cls.collection_status == "SUCCESS"
        ).order_by(snap_cls.timestamp.asc()).all()
        
        if snaps:
            snap_ids = [s.id for s in snaps]
            analytics = db.query(anal_cls).filter(
                anal_cls.source_snapshot_id.in_(snap_ids)
            ).all()
            
            anal_map = {a.source_snapshot_id: a for a in analytics}
            
            # Fetch 1-minute snapshots as high-res spot grid
            one_min_snaps = db.query(OptionChainSnapshot).filter(
                OptionChainSnapshot.symbol == symbol,
                OptionChainSnapshot.collection_status == "SUCCESS"
            ).order_by(OptionChainSnapshot.timestamp.asc()).all()
            
            one_min_grid = [(s.timestamp, s.spot_price) for s in one_min_snaps]
            
            for s in snaps:
                anal = anal_map.get(s.id)
                if not anal or not anal.market_state or anal.market_state == "NEUTRAL":
                    continue
                    
                state = anal.market_state
                if state not in grouped_outcomes:
                    continue
                    
                t0 = s.timestamp
                spot0 = s.current_spot
                direction = get_prediction_direction(state)
                
                # Fetch future spot prices from the 1m grid
                spot_15 = find_closest_spot(t0 + timedelta(minutes=15), one_min_grid, tolerance_minutes=3)
                spot_30 = find_closest_spot(t0 + timedelta(minutes=30), one_min_grid, tolerance_minutes=5)
                spot_60 = find_closest_spot(t0 + timedelta(minutes=60), one_min_grid, tolerance_minutes=5)
                
                if spot_60 is None:
                    # Not completed yet
                    continue
                    
                # Excursion details: query 1m snaps in window
                t_end = t0 + timedelta(minutes=60)
                window_snaps = [g for g in one_min_grid if t0 <= g[0] <= t_end and g[0].date() == t0.date()]
                
                best_fav = 0.0
                worst_adv = 0.0
                
                for snap_ts, spot in window_snaps:
                    diff = spot - spot0
                    if direction == "BULLISH":
                        fav = diff
                        adv = diff
                    else: # BEARISH
                        fav = -diff
                        adv = -diff
                        
                    if fav > best_fav:
                        best_fav = fav
                    if adv < worst_adv:
                        worst_adv = adv
                        
                grouped_outcomes[state].append({
                    "movement_15m_points": spot_15 - spot0 if spot_15 is not None else None,
                    "movement_30m_points": spot_30 - spot0 if spot_30 is not None else None,
                    "movement_60m_points": spot_60 - spot0,
                    "max_favorable_move_60m": best_fav,
                    "max_adverse_move_60m": worst_adv
                })

    # Construct response
    response_payload = []
    for state in states:
        response_payload.append(calculate_metrics_for_group(grouped_outcomes[state], state))
        
    return response_payload
