import logging
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.db.models import OptionChainSnapshot, OptionChainStrike
from app.engine.analytics import calculate_pcr, find_support_resistance, calculate_strengths
from app.engine.insights import compute_market_state, compute_strike_insights
from app.engine.patterns import classify_pattern_signature, calculate_pattern_confidence
from app.config import settings

logger = logging.getLogger(__name__)

def replay_historical_snapshots(
    db: Session,
    symbol: str,
    start_time: datetime,
    end_time: datetime
) -> List[Dict[str, Any]]:
    """
    Queries historical successful 1-minute snapshots and strikes chronologically,
    and runs the analytical/insights calculations in-memory step-by-step.
    """
    logger.info(f"Replaying historical snapshots for {symbol} from {start_time} to {end_time}...")
    
    snapshots = db.query(OptionChainSnapshot).filter(
        OptionChainSnapshot.symbol == symbol.upper(),
        OptionChainSnapshot.timestamp >= start_time,
        OptionChainSnapshot.timestamp <= end_time,
        OptionChainSnapshot.collection_status == "SUCCESS"
    ).order_by(OptionChainSnapshot.timestamp.asc()).all()

    if not snapshots:
        logger.info(f"No successful snapshots found for {symbol} in replay window.")
        return []

    # In-memory variables to track the previous state
    prev_spot = 0.0
    prev_oi = 0
    prev_volume = 0
    prev_avg_iv = 0.0
    prev_timestamp = None
    prev_pcr = None
    prev_ema20 = None
    prev_atr = None
    previous_pattern_id = None
    pattern_age = 0

    results = []

    for snap in snapshots:
        # Fetch strikes for this snapshot
        strikes = db.query(OptionChainStrike).filter(
            OptionChainStrike.snapshot_id == snap.id
        ).all()

        if not strikes:
            continue

        # 1. Compute PCR
        pcr = calculate_pcr(strikes)

        gap_reset = bool(
            prev_timestamp and (snap.timestamp - prev_timestamp).total_seconds() > 1800
        )

        # 2. Compute Support/Resistance (spot_price ensures supports <= spot, resistances > spot)
        s1, s2, r1, r2 = find_support_resistance(strikes, spot_price=snap.spot_price)
        s1_strength, r1_strength = calculate_strengths(strikes, s1, r1)

        # 3. Compute Spot distances
        dist_s1 = snap.spot_price - s1
        dist_r1 = r1 - snap.spot_price

        # 4. Compute Average IV
        avg_iv = sum(s.call_iv + s.put_iv for s in strikes) / (len(strikes) * 2) if strikes else 0.0

        # 5. Compute IV Change compared to previous in-memory average IV
        iv_change = 0.0
        if prev_avg_iv > 0.0:
            iv_change = ((avg_iv - prev_avg_iv) / prev_avg_iv) * 100

        # 6. Sum current open interest and volume
        oi_curr = sum(s.call_oi + s.put_oi for s in strikes)
        vol_curr = sum(s.call_volume + s.put_volume for s in strikes)

        true_range = abs(snap.spot_price - prev_spot) if prev_spot and not gap_reset else 0.0
        ema20 = (
            snap.spot_price
            if prev_ema20 is None or gap_reset
            else snap.spot_price * (2.0 / 21.0) + prev_ema20 * (19.0 / 21.0)
        )
        atr = (
            max(true_range, 1.0)
            if prev_atr is None or gap_reset
            else true_range * (2.0 / 15.0) + prev_atr * (13.0 / 15.0)
        )

        signature = classify_pattern_signature(
            spot_price=snap.spot_price,
            ema20=ema20,
            atr=atr,
            total_oi=oi_curr,
            previous_total_oi=None if gap_reset else (prev_oi or None),
            pcr=pcr,
            previous_pcr=None if gap_reset else prev_pcr,
        )
        quality_score = 100
        if not any((strike.call_iv or strike.put_iv) for strike in strikes):
            quality_score -= 40
        if pcr is None or pcr <= 0:
            quality_score -= 20
        pattern_confidence = calculate_pattern_confidence(signature, quality_score)
        if gap_reset or signature["pattern_id"] != previous_pattern_id:
            pattern_age = 1
        else:
            pattern_age += 1

        # 7. Compute Market buildup State (using previous in-memory state)
        market_state, strength = compute_market_state(
            spot_curr=snap.spot_price,
            spot_prev=prev_spot,
            oi_curr=oi_curr,
            oi_prev=prev_oi,
            vol_curr=vol_curr,
            vol_prev=prev_volume,
            timestamp_curr=snap.timestamp,
            timestamp_prev=prev_timestamp
        )

        # 8. Compute qualitative insights in-memory
        insights = compute_strike_insights(snap, strikes)

        # Record replay state
        results.append({
            "timestamp": snap.timestamp.isoformat() if snap.timestamp else None,
            "spot_price": snap.spot_price,
            "pcr": pcr,
            "iv_change": iv_change,
            "support": s1,
            "secondary_support": s2,
            "resistance": r1,
            "secondary_resistance": r2,
            "support_strength": s1_strength,
            "resistance_strength": r1_strength,
            "distance_to_support": dist_s1,
            "distance_to_resistance": dist_r1,
            "market_state": market_state,
            "strength": strength,
            "insights": [ins.insight_text for ins in insights],
            "pattern": {
                "pattern_id": signature["pattern_id"],
                "pattern_version": settings.RESEARCH_ENGINE_VERSION,
                "confidence": pattern_confidence,
                "age_snapshots": pattern_age,
                "trend_state": signature["trend_state"],
                "oi_state": signature["oi_state"],
                "pcr_state": signature["pcr_state"],
            },
            "feature_lineage": {
                "oi_change_pct": {
                    "sources": ["current.total_oi", "previous.total_oi"],
                    "value": signature["oi_change_pct"],
                },
                "pcr_change": {
                    "sources": ["current.pcr", "previous.pcr"],
                    "value": signature["pcr_change"],
                },
                "pattern_id": {
                    "sources": ["spot_price", "ema20", "atr", "oi_change_pct", "pcr_change"],
                    "value": signature["pattern_id"],
                },
            },
        })

        # Update tracking variables
        prev_spot = snap.spot_price
        prev_oi = oi_curr
        prev_volume = vol_curr
        prev_avg_iv = avg_iv
        prev_timestamp = snap.timestamp
        prev_pcr = pcr
        prev_ema20 = ema20
        prev_atr = atr
        previous_pattern_id = signature["pattern_id"]

    logger.info(f"Replay complete. Generated {len(results)} historical states.")
    return results
