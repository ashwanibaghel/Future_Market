import logging
import json
from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models import OptionChainSnapshot, OptionChainStrike, AnalyticsSnapshot, MLFeatureSnapshot, TradingSignal

logger = logging.getLogger(__name__)

def calculate_daily_options_vwap(db: Session, symbol: str, snapshot_timestamp: datetime) -> float:
    """
    Calculates options volume-weighted spot average for that calendar day:
    VWAP = Sum(Spot Price * Total Options Volume) / Sum(Total Options Volume)
    """
    start_of_day = datetime(snapshot_timestamp.year, snapshot_timestamp.month, snapshot_timestamp.day, 0, 0, 0)
    
    from sqlalchemy import func
    results = db.query(
        OptionChainSnapshot.spot_price,
        func.sum(OptionChainStrike.call_volume + OptionChainStrike.put_volume)
    ).join(
        OptionChainStrike, OptionChainSnapshot.id == OptionChainStrike.snapshot_id
    ).filter(
        OptionChainSnapshot.symbol == symbol,
        OptionChainSnapshot.collection_status == "SUCCESS",
        OptionChainSnapshot.timestamp >= start_of_day,
        OptionChainSnapshot.timestamp <= snapshot_timestamp
    ).group_by(OptionChainSnapshot.id).all()
    
    total_val = 0.0
    total_vol = 0
    for spot_price, vol in results:
        vol = vol or 0
        total_val += spot_price * vol
        total_vol += vol
        
    if total_vol == 0:
        return 0.0
    return total_val / total_vol

def generate_trading_signal(db: Session, snapshot_id: int) -> TradingSignal:
    """
    Evaluates rule-based signals (v1 rules) for a snapshot.
    Saves and returns the TradingSignal record, skipping SENSEX.
    """
    # 1. Fetch snapshot
    snapshot = db.query(OptionChainSnapshot).filter(OptionChainSnapshot.id == snapshot_id).first()
    if not snapshot:
        logger.warning(f"Snapshot with ID {snapshot_id} not found.")
        return None

    # Check if signal already exists for this snapshot
    existing = db.query(TradingSignal).filter(TradingSignal.snapshot_id == snapshot_id).first()
    if existing:
        return existing

    # 2. Fetch dependencies
    strikes = db.query(OptionChainStrike).filter(OptionChainStrike.snapshot_id == snapshot_id).all()

    # CRITICAL RULE: Skip signal generation if symbol has no option chain strikes (symbol-agnostic)
    if not strikes:
        logger.info(f"Skipping signal generation for symbol {snapshot.symbol} (Snapshot ID: {snapshot_id}) because it has no option chain strikes.")
        return None
    
    curr_analytics = db.query(AnalyticsSnapshot).filter(
        AnalyticsSnapshot.source_snapshot_id == snapshot_id
    ).first()
    
    if not curr_analytics:
        logger.warning(f"No analytics snapshot found for snapshot ID {snapshot_id}. Cannot generate signal.")
        return None

    # Fetch previous snapshot to compare spot, pcr, and total oi
    prev_snapshot = db.query(OptionChainSnapshot).filter(
        OptionChainSnapshot.symbol == snapshot.symbol,
        OptionChainSnapshot.collection_status == "SUCCESS",
        OptionChainSnapshot.id < snapshot_id
    ).order_by(OptionChainSnapshot.timestamp.desc()).first()

    # Fetch MLFeatureSnapshot to get EMA20 and EMA50
    ml_feature = db.query(MLFeatureSnapshot).filter(
        MLFeatureSnapshot.source_snapshot_id == snapshot_id,
        MLFeatureSnapshot.timeframe == "1m"
    ).first()

    # 3. Compute variables
    current_spot = snapshot.spot_price
    pcr = curr_analytics.pcr
    market_state = curr_analytics.market_state
    strength = curr_analytics.strength

    # Fallbacks for EMAs
    ema20 = ml_feature.ema20 if (ml_feature and ml_feature.ema20 is not None) else current_spot
    ema50 = ml_feature.ema50 if (ml_feature and ml_feature.ema50 is not None) else current_spot

    # Calculate VWAP
    vwap = calculate_daily_options_vwap(db, snapshot.symbol, snapshot.timestamp)
    if vwap == 0.0:
        vwap = current_spot

    # Historical comparisons
    price_up = False
    pcr_up = False
    oi_up = False

    if prev_snapshot:
        price_up = (current_spot > prev_snapshot.spot_price)
        
        prev_analytics = db.query(AnalyticsSnapshot).filter(
            AnalyticsSnapshot.source_snapshot_id == prev_snapshot.id
        ).first()
        if prev_analytics:
            pcr_up = (pcr > prev_analytics.pcr)
            
        # Total OI comparison
        curr_total_oi = sum(s.call_oi + s.put_oi for s in strikes)
        prev_strikes = db.query(OptionChainStrike).filter(
            OptionChainStrike.snapshot_id == prev_snapshot.id
        ).all()
        prev_total_oi = sum(s.call_oi + s.put_oi for s in prev_strikes)
        oi_up = (curr_total_oi > prev_total_oi)

    # 4. Evaluate rules
    above_vwap = (current_spot > vwap)
    below_vwap = (current_spot < vwap)
    
    above_ema20 = (current_spot > ema20)
    below_ema20 = (current_spot < ema20)

    market_state_bullish = market_state in ["LONG BUILD-UP", "SHORT COVERING"]
    market_state_bearish = market_state in ["SHORT BUILD-UP", "LONG UNWINDING"]
    
    price_down = not price_up if prev_snapshot else False
    pcr_down = not pcr_up if prev_snapshot else False
    strength_high_medium = strength in ["HIGH", "MEDIUM"]

    # Bullish condition matching
    bullish_conditions = [
        market_state_bullish,
        above_vwap,
        above_ema20,
        price_up,
        pcr_up,
        strength_high_medium
    ]
    matched_bullish = sum(bullish_conditions)

    # Bearish condition matching
    bearish_conditions = [
        market_state_bearish,
        below_vwap,
        below_ema20,
        price_down,
        pcr_down,
        strength_high_medium
    ]
    matched_bearish = sum(bearish_conditions)

    # Determine Signal Type
    if matched_bullish == 6:
        signal_type = "BUY_CALL"
        matched_conditions = 6
    elif matched_bearish == 6:
        signal_type = "BUY_PUT"
        matched_conditions = 6
    else:
        signal_type = "NO_TRADE"
        matched_conditions = max(matched_bullish, matched_bearish)

    total_conditions = 6

    # Reasons dict
    reasons_dict = {
        "market_state_bullish": market_state_bullish,
        "market_state_bearish": market_state_bearish,
        "above_vwap": above_vwap,
        "below_vwap": below_vwap,
        "above_ema20": above_ema20,
        "below_ema20": below_ema20,
        "price_up": price_up,
        "price_down": price_down,
        "pcr_up": pcr_up,
        "pcr_down": pcr_down,
        "strength_high_medium": strength_high_medium
    }

    # Signal inputs snapshot
    signal_inputs_dict = {
        "spot": current_spot,
        "pcr": pcr,
        "vwap": vwap,
        "ema20": ema20,
        "ema50": ema50,
        "market_state": market_state,
        "strength": strength
    }

    # Select strike if signal is generated
    suggested_strike = None
    strike_selection_reason = None
    if signal_type != "NO_TRADE" and strikes:
        closest_strike = min(strikes, key=lambda s: abs(s.strike - current_spot))
        strike_val = int(closest_strike.strike) if closest_strike.strike.is_integer() else closest_strike.strike
        suffix = " CE" if signal_type == "BUY_CALL" else " PE"
        suggested_strike = f"{strike_val}{suffix}"
        strike_selection_reason = "ATM"

    # Create record
    trading_signal = TradingSignal(
        snapshot_id=snapshot.id,
        timestamp=snapshot.timestamp,
        symbol=snapshot.symbol,
        expiry_date=snapshot.expiry_date,
        spot_price=current_spot,
        signal_type=signal_type,
        suggested_strike=suggested_strike,
        strike_selection_reason=strike_selection_reason,
        matched_conditions=matched_conditions,
        total_conditions=total_conditions,
        reasons=json.dumps(reasons_dict),
        signal_inputs=json.dumps(signal_inputs_dict),
        market_state=market_state,
        signal_version="v1",
        was_executed=False,
        status="PENDING"
    )

    db.add(trading_signal)
    db.commit()
    db.refresh(trading_signal)

    logger.info(f"Generated TradingSignal ID {trading_signal.id} ({signal_type}) for {snapshot.symbol} at {snapshot.timestamp}")

    # Create ObservationLog entry for active signals
    if signal_type in ["BUY_CALL", "BUY_PUT"]:
        try:
            from app.db.models import ObservationLog
            obs_log = ObservationLog(
                timestamp=snapshot.timestamp,
                symbol=snapshot.symbol,
                spot_price=current_spot,
                market_state=market_state,
                system_signal=signal_type,
                manual_signal="NO_RECORD",
                suggested_strike=suggested_strike,
                system_signal_id=trading_signal.id,
                status="PENDING"
            )
            db.add(obs_log)
            db.commit()
            logger.info(f"Created ObservationLog entry for system signal ID {trading_signal.id}")
        except Exception as oe:
            logger.error(f"Failed to create ObservationLog entry: {str(oe)}")

    return trading_signal
