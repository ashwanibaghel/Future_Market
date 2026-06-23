import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.db.models import ManualTraderDecision, TradingSignal, OptionChainSnapshot, AnalyticsSnapshot, ObservationLog

logger = logging.getLogger(__name__)

router = APIRouter()

class ManualDecisionCreate(BaseModel):
    symbol: str = Field(..., description="Symbol (e.g. NIFTY, SENSEX)")
    expiry_date: Optional[str] = Field(None, description="Expiry date in format YYYY-MM-DD or DD-MMM-YYYY")
    spot_price: Optional[float] = Field(None, description="Spot price at the time of decision (optional)")
    decision_type: str = Field(..., description="Decision: BUY_CALL, BUY_PUT, STAY_OUT")
    suggested_strike: Optional[str] = Field(None, description="Strike price (e.g., 25000 CE)")
    confidence_level: str = Field(..., description="Confidence: LOW, MEDIUM, HIGH")
    notes: Optional[Dict[str, Any]] = Field(None, description="Structured reasons as JSON dict")

@router.post("/manual-decisions")
def create_manual_decision(body: ManualDecisionCreate, db: Session = Depends(get_db)):
    """
    Records a manual trader decision (Uncle Ji's observation).
    Automatically maps to system signals generated within +/- 5 minutes and inserts an ObservationLog.
    """
    now = datetime.utcnow()
    
    # 1. Resolve Spot Price and Expiry if not provided
    spot = body.spot_price
    expiry = body.expiry_date
    market_state = "NEUTRAL"
    latest_snapshot_id = None
    
    latest_snap = db.query(OptionChainSnapshot).filter(
        OptionChainSnapshot.symbol == body.symbol,
        OptionChainSnapshot.collection_status == "SUCCESS"
    ).order_by(OptionChainSnapshot.timestamp.desc()).first()
    
    if latest_snap:
        latest_snapshot_id = latest_snap.id
        if spot is None:
            spot = latest_snap.spot_price
        if expiry is None:
            expiry = latest_snap.expiry_date
            
        # Get market state
        analytics = db.query(AnalyticsSnapshot).filter(
            AnalyticsSnapshot.source_snapshot_id == latest_snap.id
        ).first()
        if analytics and analytics.market_state:
            market_state = analytics.market_state
            
    if spot is None:
        spot = 0.0
    if expiry is None:
        expiry = "N/A"
        
    # 2. Check for matched system signal generated within +/- 5 minutes
    t_min = now - timedelta(minutes=5)
    t_max = now + timedelta(minutes=5)
    
    matched_signal = db.query(TradingSignal).filter(
        TradingSignal.symbol == body.symbol,
        TradingSignal.timestamp >= t_min,
        TradingSignal.timestamp <= t_max
    ).order_by(TradingSignal.timestamp.desc()).first()
    
    matched_signal_id = matched_signal.id if matched_signal else None
    system_signal_type = matched_signal.signal_type if matched_signal else "NO_TRADE"
    
    # 3. Create Manual Decision record
    notes_str = json.dumps(body.notes) if body.notes else None
    
    decision = ManualTraderDecision(
        timestamp=now,
        symbol=body.symbol,
        expiry_date=expiry,
        spot_price=spot,
        decision_type=body.decision_type,
        suggested_strike=body.suggested_strike,
        confidence_level=body.confidence_level,
        notes=notes_str,
        matched_system_signal_id=matched_signal_id,
        was_executed=True,
        status="PENDING"
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)
    
    # 4. Create corresponding ObservationLog entry
    obs_log = ObservationLog(
        timestamp=now,
        symbol=body.symbol,
        spot_price=spot,
        market_state=market_state,
        system_signal=system_signal_type,
        manual_signal=body.decision_type,
        suggested_strike=body.suggested_strike,
        notes=notes_str,
        manual_decision_id=decision.id,
        system_signal_id=matched_signal_id,
        status="PENDING"
    )
    db.add(obs_log)
    db.commit()
    
    logger.info(f"Recorded manual decision ID {decision.id} and created ObservationLog entry.")
    
    return {
        "status": "success",
        "decision_id": decision.id,
        "matched_signal_id": matched_signal_id,
        "system_signal": system_signal_type
    }

@router.get("/manual-decisions")
def get_manual_decisions(symbol: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """
    Returns list of logged manual decisions.
    """
    query = db.query(ManualTraderDecision)
    if symbol:
        query = query.filter(ManualTraderDecision.symbol == symbol)
    return query.order_by(ManualTraderDecision.timestamp.desc()).all()

@router.get("/manual-decisions/compare")
def compare_performance(symbol: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """
    Compares the predictive performance of Uncle Ji's manual decisions against the system.
    """
    query = db.query(ManualTraderDecision).filter(ManualTraderDecision.decision_type.in_(["BUY_CALL", "BUY_PUT"]))
    if symbol:
        query = query.filter(ManualTraderDecision.symbol == symbol)
        
    decisions = query.all()
    total = len(decisions)
    
    resolved = [d for d in decisions if d.status == "COMPLETED"]
    resolved_count = len(resolved)
    
    wins = sum(1 for d in resolved if d.outcome_60m == "WIN" or (d.outcome_60m == "PENDING" and (d.outcome_30m == "WIN" or d.outcome_15m == "WIN")))
    losses = sum(1 for d in resolved if d.outcome_60m == "LOSS" or (d.outcome_60m == "PENDING" and (d.outcome_30m == "LOSS" or d.outcome_15m == "LOSS")))
    flats = resolved_count - wins - losses
    
    win_rate = (wins / resolved_count * 100) if resolved_count > 0 else 0.0
    
    # Compare with matched system signals
    agreed_count = 0
    agreed_wins = 0
    agreed_resolved = 0
    
    disagreed_count = 0
    disagreed_wins = 0
    disagreed_resolved = 0
    
    for d in decisions:
        if d.matched_system_signal_id:
            sig = db.query(TradingSignal).filter(TradingSignal.id == d.matched_system_signal_id).first()
            if sig:
                # System agreed if signals match (BUY_CALL == BUY_CALL, BUY_PUT == BUY_PUT)
                is_agreed = (d.decision_type == sig.signal_type)
                
                # Check resolved status
                is_resolved = (d.status == "COMPLETED")
                is_win = d.outcome_60m == "WIN" or (d.outcome_60m == "PENDING" and (d.outcome_30m == "WIN" or d.outcome_15m == "WIN"))
                
                if is_agreed:
                    agreed_count += 1
                    if is_resolved:
                        agreed_resolved += 1
                        if is_win:
                            agreed_wins += 1
                else:
                    disagreed_count += 1
                    if is_resolved:
                        disagreed_resolved += 1
                        if is_win:
                            disagreed_wins += 1
        else:
            # No system signal matched (effectively disagreed as system was NO_TRADE)
            disagreed_count += 1
            if d.status == "COMPLETED":
                disagreed_resolved += 1
                is_win = d.outcome_60m == "WIN" or (d.outcome_60m == "PENDING" and (d.outcome_30m == "WIN" or d.outcome_15m == "WIN"))
                if is_win:
                    disagreed_wins += 1

    agreed_win_rate = (agreed_wins / agreed_resolved * 100) if agreed_resolved > 0 else 0.0
    disagreed_win_rate = (disagreed_wins / disagreed_resolved * 100) if disagreed_resolved > 0 else 0.0

    return {
        "manual_stats": {
            "total_decisions": total,
            "resolved_decisions": resolved_count,
            "wins": wins,
            "losses": losses,
            "flats": flats,
            "win_rate_pct": round(win_rate, 2)
        },
        "comparison_stats": {
            "agreed_total": agreed_count,
            "agreed_resolved": agreed_resolved,
            "agreed_wins": agreed_wins,
            "agreed_win_rate_pct": round(agreed_win_rate, 2),
            "disagreed_total": disagreed_count,
            "disagreed_resolved": disagreed_resolved,
            "disagreed_wins": disagreed_wins,
            "disagreed_win_rate_pct": round(disagreed_win_rate, 2)
        }
    }
