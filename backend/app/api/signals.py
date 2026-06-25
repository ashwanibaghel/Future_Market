import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.db.models import TradingSignal, OptionChainSnapshot

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/signals/latest")
def get_latest_signal(symbol: str = Query(..., description="Symbol (e.g. NIFTY, SENSEX)"), date: str = Query(None, description="Date in YYYY-MM-DD format"), db: Session = Depends(get_db)):
    """
    Returns the latest signal generated (or NO_TRADE) along with strike, confidence, reasons, and timestamp.
    """


    query = db.query(TradingSignal).filter(TradingSignal.symbol == symbol)
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
            query = query.filter(func.date(TradingSignal.timestamp) == target_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
            
    latest_signal = query.order_by(TradingSignal.timestamp.desc()).first()
    if not latest_signal:
        latest_snap = db.query(OptionChainSnapshot).filter(
            OptionChainSnapshot.symbol == symbol,
            OptionChainSnapshot.collection_status == "SUCCESS"
        ).order_by(OptionChainSnapshot.timestamp.desc()).first()
        spot = latest_snap.spot_price if latest_snap else 0.0
        
        return {
            "id": 0,
            "snapshot_id": latest_snap.id if latest_snap else 0,
            "timestamp": latest_snap.timestamp if latest_snap else datetime.utcnow(),
            "symbol": symbol,
            "expiry_date": latest_snap.expiry_date if latest_snap else "N/A",
            "spot_price": spot,
            "signal_type": "NO_TRADE",
            "suggested_strike": None,
            "strike_selection_reason": None,
            "matched_conditions": 0,
            "total_conditions": 6,
            "reasons": json.dumps({}),
            "signal_inputs": json.dumps({
                "spot": spot,
                "pcr": 0.0,
                "vwap": 0.0,
                "ema20": spot,
                "ema50": spot,
                "market_state": "NEUTRAL",
                "strength": "LOW"
            }),
            "market_state": "NEUTRAL",
            "signal_version": "v1",
            "was_executed": False,
            "outcome_15m": "PENDING",
            "outcome_30m": "PENDING",
            "outcome_60m": "PENDING",
            "status": "PENDING"
        }
    return latest_signal

@router.get("/signals/stats")
def get_signals_stats(symbol: str = Query(..., description="Symbol (e.g. NIFTY, SENSEX)"), db: Session = Depends(get_db)):
    """
    Returns signals predictive performance statistics.
    """


    active_signals = db.query(TradingSignal).filter(
        TradingSignal.symbol == symbol,
        TradingSignal.signal_type.in_(["BUY_CALL", "BUY_PUT"])
    ).all()
    
    total = len(active_signals)
    
    # Timeframe accuracy
    tf_stats = {}
    for tf in ["15m", "30m", "60m"]:
        tf_total = 0
        tf_wins = 0
        tf_losses = 0
        tf_flats = 0
        for sig in active_signals:
            outcome = getattr(sig, f"outcome_{tf}")
            if outcome != "PENDING":
                tf_total += 1
                if outcome == "WIN":
                    tf_wins += 1
                elif outcome == "LOSS":
                    tf_losses += 1
                elif outcome == "FLAT":
                    tf_flats += 1
        acc = (tf_wins / tf_total * 100) if tf_total > 0 else 0.0
        tf_stats[tf] = {
            "total": tf_total,
            "wins": tf_wins,
            "losses": tf_losses,
            "flats": tf_flats,
            "accuracy_pct": round(acc, 2)
        }
        
    # State accuracy (using 60m or latest resolved outcome)
    state_stats = {}
    states = list(set(sig.market_state for sig in active_signals if sig.market_state))
    for state in states:
        state_total = 0
        state_wins = 0
        for sig in active_signals:
            if sig.market_state == state:
                outcome = sig.outcome_60m if sig.outcome_60m != "PENDING" else (sig.outcome_30m if sig.outcome_30m != "PENDING" else sig.outcome_15m)
                if outcome != "PENDING":
                    state_total += 1
                    if outcome == "WIN":
                        state_wins += 1
        acc = (state_wins / state_total * 100) if state_total > 0 else 0.0
        state_stats[state] = {
            "total": state_total,
            "wins": state_wins,
            "accuracy_pct": round(acc, 2)
        }
        
    # Overall Accuracy
    overall_total = 0
    overall_wins = 0
    overall_losses = 0
    overall_flats = 0
    for sig in active_signals:
        outcome = sig.outcome_60m if sig.outcome_60m != "PENDING" else (sig.outcome_30m if sig.outcome_30m != "PENDING" else sig.outcome_15m)
        if outcome != "PENDING":
            overall_total += 1
            if outcome == "WIN":
                overall_wins += 1
            elif outcome == "LOSS":
                overall_losses += 1
            elif outcome == "FLAT":
                overall_flats += 1
                
    overall_acc = (overall_wins / overall_total * 100) if overall_total > 0 else 0.0
    
    return {
        "symbol": symbol,
        "total_signals": total,
        "resolved_signals": overall_total,
        "wins": overall_wins,
        "losses": overall_losses,
        "flats": overall_flats,
        "overall_accuracy_pct": round(overall_acc, 2),
        "timeframe_accuracy": tf_stats,
        "state_accuracy": state_stats
    }

@router.get("/signals/history")
def get_signals_history(
    symbol: str = Query(..., description="Symbol (e.g. NIFTY)"),
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    db: Session = Depends(get_db)
):
    """
    Returns signals history (BUY_CALL/BUY_PUT active recommendations).
    """
    query = db.query(TradingSignal).filter(
        TradingSignal.symbol == symbol,
        TradingSignal.signal_type.in_(["BUY_CALL", "BUY_PUT"])
    )
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
            query = query.filter(func.date(TradingSignal.timestamp) == target_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
            
    return query.order_by(TradingSignal.timestamp.desc()).all()

@router.post("/signals/{signal_id}/execute")
def execute_signal(signal_id: int, db: Session = Depends(get_db)):
    """
    Marks that a signal was executed by the user.
    """
    signal = db.query(TradingSignal).filter(TradingSignal.id == signal_id).first()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    signal.was_executed = True
    db.commit()
    db.refresh(signal)
    return {"status": "success", "was_executed": signal.was_executed}
