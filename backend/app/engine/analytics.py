import logging
from typing import List, Tuple, Dict, Any
from sqlalchemy.orm import Session
from app.db.models import OptionChainSnapshot, OptionChainStrike, AnalyticsSnapshot

logger = logging.getLogger(__name__)

def calculate_pcr(strikes: List[OptionChainStrike]) -> float:
    """
    PCR = Total Put OI / Total Call OI
    """
    total_call_oi = sum(s.call_oi for s in strikes)
    total_put_oi = sum(s.put_oi for s in strikes)
    
    if total_call_oi == 0:
        return 0.0
    return float(total_put_oi / total_call_oi)

def find_support_resistance(strikes: List[Any], spot_price: float = 0.0) -> Tuple[float, float, float, float]:
    """
    Returns (Primary Support, Secondary Support, Primary Resistance, Secondary Resistance)

    CRITICAL RULE:
    - Support levels MUST be at or BELOW the current spot price (put writers defend levels below spot)
    - Resistance levels MUST be ABOVE the current spot price (call writers cap levels above spot)

    Levels are selected using a weighted combination of total Open Interest (OI)
    and intraday Open Interest change (Change OI) based on config settings.

    score = (OI * OI_WEIGHT) + (Change_OI * CHANGE_OI_WEIGHT)
    """
    if not strikes:
        return 0.0, 0.0, 0.0, 0.0

    from app.config import settings
    oi_w = settings.OI_WEIGHT
    coi_w = settings.CHANGE_OI_WEIGHT

    # Filter strikes: support candidates are AT or BELOW spot, resistance candidates are ABOVE spot
    if spot_price > 0:
        support_strikes = [s for s in strikes if s.strike <= spot_price]
        resistance_strikes = [s for s in strikes if s.strike > spot_price]
    else:
        # Fallback: no spot price available, use all strikes (legacy behaviour)
        support_strikes = strikes
        resistance_strikes = strikes

    # If filtering yields no candidates, fall back to full chain to avoid empty results
    if not support_strikes:
        support_strikes = strikes
    if not resistance_strikes:
        resistance_strikes = strikes

    # Support: highest Put weighted score among strikes AT/BELOW spot
    sorted_puts = sorted(support_strikes, key=lambda s: (s.put_oi * oi_w) + (s.put_change_oi * coi_w), reverse=True)
    primary_support = sorted_puts[0].strike
    # S2 must be BELOW S1 (deeper support), pick the highest scoring put below primary_support
    s2_candidates = [s for s in sorted_puts[1:] if s.strike < primary_support]
    secondary_support = s2_candidates[0].strike if s2_candidates else primary_support

    # Resistance: highest Call weighted score among strikes ABOVE spot
    sorted_calls = sorted(resistance_strikes, key=lambda s: (s.call_oi * oi_w) + (s.call_change_oi * coi_w), reverse=True)
    primary_resistance = sorted_calls[0].strike
    # R2 must be ABOVE R1 (deeper resistance), pick the highest scoring call above primary_resistance
    r2_candidates = [s for s in sorted_calls[1:] if s.strike > primary_resistance]
    secondary_resistance = r2_candidates[0].strike if r2_candidates else primary_resistance

    return primary_support, secondary_support, primary_resistance, secondary_resistance

def calculate_strengths(strikes: List[OptionChainStrike], s1: float, r1: float) -> Tuple[str, str]:
    """
    Determines strength of S1 and R1 levels.
    S1 Strength: If Put OI at S1 is > 15% of total Put OI -> HIGH, > 10% -> MEDIUM, else LOW.
    R1 Strength: If Call OI at R1 is > 15% of total Call OI -> HIGH, > 10% -> MEDIUM, else LOW.
    """
    total_put_oi = sum(s.put_oi for s in strikes)
    total_call_oi = sum(s.call_oi for s in strikes)

    s1_oi = next((s.put_oi for s in strikes if s.strike == s1), 0)
    r1_oi = next((s.call_oi for s in strikes if s.strike == r1), 0)

    # Support Strength
    if total_put_oi == 0:
        s1_strength = "LOW"
    else:
        s1_ratio = s1_oi / total_put_oi
        if s1_ratio > 0.15:
            s1_strength = "HIGH"
        elif s1_ratio > 0.10:
            s1_strength = "MEDIUM"
        else:
            s1_strength = "LOW"

    # Resistance Strength
    if total_call_oi == 0:
        r1_strength = "LOW"
    else:
        r1_ratio = r1_oi / total_call_oi
        if r1_ratio > 0.15:
            r1_strength = "HIGH"
        elif r1_ratio > 0.10:
            r1_strength = "MEDIUM"
        else:
            r1_strength = "LOW"

    return s1_strength, r1_strength

def calculate_iv_change(db: Session, symbol: str, expiry_date: str, current_avg_iv: float) -> float:
    """
    Calculates change in Implied Volatility compared to the previous successful snapshot.
    """
    return calculate_iv_change_generic(
        db, symbol, expiry_date, current_avg_iv, OptionChainSnapshot, OptionChainStrike
    )

def calculate_iv_change_generic(
    db: Session,
    symbol: str,
    expiry_date: str,
    current_avg_iv: float,
    snapshot_cls,
    strike_cls
) -> float:
    """
    Generic version of IV change calculation supporting 1m, 5m, 15m classes.
    """
    # Fetch the previous snapshot
    prev_snapshot = db.query(snapshot_cls).filter(
        snapshot_cls.symbol == symbol,
        snapshot_cls.expiry_date == expiry_date,
        snapshot_cls.collection_status == "SUCCESS"
    ).order_by(snapshot_cls.timestamp.desc()).offset(1).first()

    if not prev_snapshot:
        return 0.0

    # Fetch strikes for previous snapshot to calculate average IV
    prev_strikes = db.query(strike_cls).filter(
        strike_cls.snapshot_id == prev_snapshot.id
    ).all()

    if not prev_strikes:
        return 0.0

    # Calculate average IV (average of CE and PE IVs)
    prev_total_iv = sum(s.call_iv + s.put_iv for s in prev_strikes)
    prev_avg_iv = prev_total_iv / (len(prev_strikes) * 2)

    if prev_avg_iv == 0.0:
        return 0.0

    # Return percentage change
    return ((current_avg_iv - prev_avg_iv) / prev_avg_iv) * 100

def generate_analytics_snapshot(db: Session, snapshot_id: int) -> AnalyticsSnapshot:
    """
    Computes all options analytics for a 1-minute snapshot and saves the AnalyticsSnapshot record.
    """
    return generate_analytics_snapshot_generic(
        db, snapshot_id, OptionChainSnapshot, OptionChainStrike, AnalyticsSnapshot, run_insights=True
    )

def generate_analytics_snapshot_generic(
    db: Session,
    snapshot_id: int,
    snapshot_cls,
    strike_cls,
    analytics_cls,
    run_insights: bool = False
):
    """
    Generic analytics computation for a snapshot (1m, 5m, 15m) that saves to the respective analytics table.
    """
    from app.engine.insights import compute_market_state, generate_strike_insights

    snapshot = db.query(snapshot_cls).filter(snapshot_cls.id == snapshot_id).first()
    if not snapshot:
        raise ValueError(f"Snapshot with ID {snapshot_id} not found in {snapshot_cls.__name__}")

    strikes = db.query(strike_cls).filter(strike_cls.snapshot_id == snapshot_id).all()
    if not strikes:
        raise ValueError(f"No strikes found for snapshot ID {snapshot_id} in {strike_cls.__name__}")

    # Compute PCR
    pcr = calculate_pcr(strikes)

    # Compute Support and Resistance (spot_price ensures supports < spot, resistances > spot)
    s1, s2, r1, r2 = find_support_resistance(strikes, spot_price=snapshot.spot_price)

    # Compute S1 and R1 Strengths
    s1_strength, r1_strength = calculate_strengths(strikes, s1, r1)

    # Compute average IV of the current snapshot
    current_total_iv = sum(s.call_iv + s.put_iv for s in strikes)
    current_avg_iv = current_total_iv / (len(strikes) * 2) if strikes else 0.0

    # Compute IV Change
    iv_change = calculate_iv_change_generic(
        db, snapshot.symbol, snapshot.expiry_date, current_avg_iv, snapshot_cls, strike_cls
    )

    # Distances
    distance_to_support = snapshot.spot_price - s1
    distance_to_resistance = r1 - snapshot.spot_price

    # Fetch previous snapshot for buildup calculations
    prev_snapshot = db.query(snapshot_cls).filter(
        snapshot_cls.symbol == snapshot.symbol,
        snapshot_cls.expiry_date == snapshot.expiry_date,
        snapshot_cls.collection_status == "SUCCESS",
        snapshot_cls.id < snapshot.id
    ).order_by(snapshot_cls.timestamp.desc()).first()

    oi_curr = sum(s.call_oi + s.put_oi for s in strikes)
    vol_curr = sum(s.call_volume + s.put_volume for s in strikes)

    if prev_snapshot:
        prev_strikes = db.query(strike_cls).filter(strike_cls.snapshot_id == prev_snapshot.id).all()
        oi_prev = sum(s.call_oi + s.put_oi for s in prev_strikes)
        vol_prev = sum(s.call_volume + s.put_volume for s in prev_strikes)
        spot_prev = prev_snapshot.spot_price
        timestamp_prev = prev_snapshot.timestamp
    else:
        oi_prev = 0
        vol_prev = 0
        spot_prev = 0.0
        timestamp_prev = None

    # Compute Market State (Buildup & Strength)
    market_state, strength = compute_market_state(
        spot_curr=snapshot.spot_price,
        spot_prev=spot_prev,
        oi_curr=oi_curr,
        oi_prev=oi_prev,
        vol_curr=vol_curr,
        vol_prev=vol_prev,
        timestamp_curr=snapshot.timestamp,
        timestamp_prev=timestamp_prev
    )

    # Create AnalyticsSnapshot record
    analytics_rec = analytics_cls(
        timestamp=snapshot.timestamp,
        symbol=snapshot.symbol,
        instrument_type=snapshot.instrument_type,
        expiry_date=snapshot.expiry_date,
        source_snapshot_id=snapshot.id,
        current_spot=snapshot.spot_price,
        pcr=pcr,
        iv_change=iv_change,
        support=s1,
        secondary_support=s2,
        resistance=r1,
        secondary_resistance=r2,
        distance_to_support=distance_to_support,
        distance_to_resistance=distance_to_resistance,
        support_strength=s1_strength,
        resistance_strength=r1_strength,
        market_state=market_state,
        strength=strength
    )

    db.add(analytics_rec)
    
    # Generate strike-level qualitative insights & outcomes
    if run_insights:
        try:
            generate_strike_insights(db, snapshot, strikes)
        except Exception as ge:
            logger.exception(f"Failed to generate strike-level insights: {str(ge)}")
            
        from app.engine.outcomes import create_pending_outcome
        try:
            create_pending_outcome(db, snapshot, market_state)
        except Exception as oe:
            logger.exception(f"Failed to create pending outcome: {str(oe)}")
            
    db.commit()
    db.refresh(analytics_rec)
    
    logger.info(f"Generated {analytics_cls.__name__} ID {analytics_rec.id} for {snapshot.symbol}")
    return analytics_rec

