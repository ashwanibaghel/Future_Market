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
def get_latest_signal(
    symbol: str = Query(..., description="Symbol (e.g. NIFTY, SENSEX)"),
    date: str = Query(None, description="Date in YYYY-MM-DD format"),
    version: str = Query("v2", description="Signal engine version (v2, v2.5)"),
    db: Session = Depends(get_db)
):
    """
    Returns the latest signal generated (or NO_TRADE) along with strike, confidence, reasons, and timestamp.
    """


    query = db.query(TradingSignal).filter(
        TradingSignal.symbol == symbol,
        TradingSignal.signal_version == version
    )
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
            "signal_version": version,
            "was_executed": False,
            "outcome_15m": "PENDING",
            "outcome_30m": "PENDING",
            "outcome_60m": "PENDING",
            "status": "PENDING",
            "expected_strength": "Weak Setup",
            "closest_failed_rule": None
        }
    return latest_signal

@router.get("/signals/stats")
def get_signals_stats(
    symbol: str = Query(..., description="Symbol (e.g. NIFTY, SENSEX)"),
    version: str = Query("v2", description="Signal engine version (v2, v2.5)"),
    db: Session = Depends(get_db)
):
    """
    Returns signals predictive performance statistics.
    """


    active_signals = db.query(TradingSignal).filter(
        TradingSignal.symbol == symbol,
        TradingSignal.signal_version == version,
        TradingSignal.signal_type.in_(["BUY_CALL", "BUY_PUT"])
    ).all()
    
    total = len(active_signals)
    
    # Timeframe accuracy (excluding FLATS from win rate denominator)
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
        tf_decisive = tf_wins + tf_losses
        acc = (tf_wins / tf_decisive * 100) if tf_decisive > 0 else 0.0
        tf_stats[tf] = {
            "total": tf_total,
            "wins": tf_wins,
            "losses": tf_losses,
            "flats": tf_flats,
            "accuracy_pct": round(acc, 2)
        }
        
    # State accuracy (using 60m or latest resolved outcome, excluding FLATS)
    state_stats = {}
    states = list(set(sig.market_state for sig in active_signals if sig.market_state))
    for state in states:
        state_total = 0
        state_wins = 0
        for sig in active_signals:
            if sig.market_state == state:
                outcome = sig.outcome_60m if sig.outcome_60m != "PENDING" else (sig.outcome_30m if sig.outcome_30m != "PENDING" else sig.outcome_15m)
                if outcome in ["WIN", "LOSS"]:
                    state_total += 1
                    if outcome == "WIN":
                        state_wins += 1
        acc = (state_wins / state_total * 100) if state_total > 0 else 0.0
        state_stats[state] = {
            "total": state_total,
            "wins": state_wins,
            "accuracy_pct": round(acc, 2)
        }
        
    # Overall Accuracy (excluding FLATS from win rate denominator)
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
                
    overall_decisive = overall_wins + overall_losses
    overall_acc = (overall_wins / overall_decisive * 100) if overall_decisive > 0 else 0.0

    # Query last 1000 signals of this version for rich metrics
    all_signals = db.query(TradingSignal).filter(
        TradingSignal.symbol == symbol,
        TradingSignal.signal_version == version
    ).order_by(TradingSignal.timestamp.desc()).limit(1000).all()

    # 1. Rejection reasons
    rejections = {}
    no_trade_count = 0
    for sig in all_signals:
        if sig.signal_type == "NO_TRADE":
            no_trade_count += 1
            if sig.closest_failed_rule:
                rejections[sig.closest_failed_rule] = rejections.get(sig.closest_failed_rule, 0) + 1
    rejections_pct = {k: round(v / no_trade_count * 100, 2) for k, v in rejections.items()} if no_trade_count > 0 else {}

    # 2. Rule Importance
    rule_counts = {}
    rule_totals = 0
    for sig in all_signals:
        if sig.reasons:
            try:
                r_dict = json.loads(sig.reasons)
                rule_totals += 1
                for r_name, r_data in r_dict.items():
                    contrib = r_data.get("contribution", 0.0)
                    if contrib > 0.0:
                        rule_counts[r_name] = rule_counts.get(r_name, 0) + 1
            except Exception:
                pass
    rule_importance = {k: round(v / rule_totals * 100, 2) for k, v in rule_counts.items()} if rule_totals > 0 else {}

    # 3. Score Calibration Win Rates
    score_bands = {
        "50-60": {"wins": 0, "total": 0},
        "60-70": {"wins": 0, "total": 0},
        "70-80": {"wins": 0, "total": 0},
        "80-90": {"wins": 0, "total": 0},
        "90-100": {"wins": 0, "total": 0}
    }
    for sig in all_signals:
        if sig.signal_type in ["BUY_CALL", "BUY_PUT"]:
            score = sig.bullish_score if sig.signal_type == "BUY_CALL" else sig.bearish_score
            if score is None:
                continue
            outcome = sig.outcome_60m if sig.outcome_60m != "PENDING" else (sig.outcome_30m if sig.outcome_30m != "PENDING" else sig.outcome_15m)
            if outcome in ["WIN", "LOSS"]:
                band = None
                if 50 <= score < 60:
                    band = "50-60"
                elif 60 <= score < 70:
                    band = "60-70"
                elif 70 <= score < 80:
                    band = "70-80"
                elif 80 <= score < 90:
                    band = "80-90"
                elif 90 <= score <= 100:
                    band = "90-100"
                
                if band:
                    score_bands[band]["total"] += 1
                    if outcome == "WIN":
                        score_bands[band]["wins"] += 1
                        
    score_calibration = {}
    for band, data in score_bands.items():
        win_rate = round(data["wins"] / data["total"] * 100, 2) if data["total"] > 0 else 0.0
        score_calibration[band] = {
            "wins": data["wins"],
            "total": data["total"],
            "win_rate_pct": win_rate
        }

    # 4. Feature distribution statistics
    feature_vals = {
        "pcr": [],
        "volume_z_score": [],
        "net_delta_bias": [],
        "delta_oi": []
    }
    for sig in all_signals:
        try:
            inputs = json.loads(sig.signal_inputs)
            raw = inputs.get("raw_features", inputs)
            pcr_val = raw.get("pcr")
            if pcr_val is not None: feature_vals["pcr"].append(pcr_val)
            
            vz = raw.get("volume_z_score")
            if vz is not None: feature_vals["volume_z_score"].append(vz)
            
            nd = raw.get("net_delta_bias")
            if nd is not None: feature_vals["net_delta_bias"].append(nd)
            
            reasons_dict = json.loads(sig.reasons) if sig.reasons else {}
            oi_raw_str = reasons_dict.get("OI Change", {}).get("raw", "")
            if "delta_oi=" in oi_raw_str:
                parts = oi_raw_str.split(",")
                delta_str = parts[0].replace("delta_oi=", "").replace("%", "").strip()
                feature_vals["delta_oi"].append(float(delta_str) / 100.0)
        except Exception:
            pass
            
    feature_distribution = {}
    for feat, vals in feature_vals.items():
        if vals:
            n = len(vals)
            f_mean = sum(vals) / n
            f_min = min(vals)
            f_max = max(vals)
            f_var = sum((x - f_mean) ** 2 for x in vals) / n
            f_std = math.sqrt(f_var)
            feature_distribution[feat] = {
                "mean": round(f_mean, 4),
                "stddev": round(f_std, 4),
                "min": round(f_min, 4),
                "max": round(f_max, 4),
                "count": n
            }
        else:
            feature_distribution[feat] = {"mean": 0, "stddev": 0, "min": 0, "max": 0, "count": 0}

    # 5. Rule Correlation Matrix
    rule_series = {
        "VWAP": [],
        "EMA": [],
        "Momentum": [],
        "PCR": [],
        "OI": []
    }
    for sig in all_signals:
        if sig.reasons:
            try:
                r_dict = json.loads(sig.reasons)
                v_val = r_dict.get("VWAP Distance", {}).get("contribution", 0.0)
                e_val = r_dict.get("EMA Trends", {}).get("contribution", 0.0)
                m_val = r_dict.get("Price Momentum", {}).get("contribution", 0.0)
                p_val = r_dict.get("PCR Trend", {}).get("contribution", 0.0)
                o_val = r_dict.get("OI Change", {}).get("contribution", 0.0)
                
                rule_series["VWAP"].append(v_val)
                rule_series["EMA"].append(e_val)
                rule_series["Momentum"].append(m_val)
                rule_series["PCR"].append(p_val)
                rule_series["OI"].append(o_val)
            except Exception:
                pass
                
    def pearson_corr(X, Y):
        if not X or not Y or len(X) != len(Y):
            return 0.0
        n = len(X)
        mean_x = sum(X) / n
        mean_y = sum(Y) / n
        cov = sum((X[i] - mean_x) * (Y[i] - mean_y) for i in range(n))
        var_x = sum((X[i] - mean_x) ** 2 for i in range(n))
        var_y = sum((Y[i] - mean_y) ** 2 for i in range(n))
        if var_x == 0.0 or var_y == 0.0:
            return 0.0
        return round(cov / math.sqrt(var_x * var_y), 4)
        
    rule_correlation = {
        "VWAP_vs_EMA": pearson_corr(rule_series["VWAP"], rule_series["EMA"]),
        "EMA_vs_Momentum": pearson_corr(rule_series["EMA"], rule_series["Momentum"]),
        "PCR_vs_OI": pearson_corr(rule_series["PCR"], rule_series["OI"])
    }
    
    return {
        "symbol": symbol,
        "total_signals": total,
        "resolved_signals": overall_total,
        "wins": overall_wins,
        "losses": overall_losses,
        "flats": overall_flats,
        "overall_accuracy_pct": round(overall_acc, 2),
        "timeframe_accuracy": tf_stats,
        "state_accuracy": state_stats,
        "rejection_analytics": rejections_pct,
        "rule_importance": rule_importance,
        "rule_correlation": rule_correlation,
        "feature_distribution": feature_distribution,
        "score_calibration": score_calibration
    }

@router.get("/signals/history")
def get_signals_history(
    symbol: str = Query(..., description="Symbol (e.g. NIFTY)"),
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    version: str = Query("v2", description="Signal engine version (v2, v2.5)"),
    db: Session = Depends(get_db)
):
    """
    Returns signals history (BUY_CALL/BUY_PUT active recommendations).
    """
    query = db.query(TradingSignal).filter(
        TradingSignal.symbol == symbol,
        TradingSignal.signal_version == version,
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
