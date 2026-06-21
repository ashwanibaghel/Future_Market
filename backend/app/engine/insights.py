import logging
from datetime import datetime, timedelta
from typing import Tuple, List, Dict, Any
from sqlalchemy.orm import Session
from app.db.models import OptionChainSnapshot, OptionChainStrike, AnalyticsSnapshot, GeneratedInsight

logger = logging.getLogger(__name__)

def compute_market_state(
    spot_curr: float,
    spot_prev: float,
    oi_curr: int,
    oi_prev: int,
    vol_curr: int,
    vol_prev: int,
    timestamp_curr: datetime,
    timestamp_prev: datetime
) -> Tuple[str, str]:
    """
    Computes overall market buildup state based on changes in spot price and Open Interest.
    Includes time gap validation to handle weekends/overnight halts safely.
    Returns: (market_state, strength)
    """
    # 1. Time Gap Safety Check
    if not timestamp_prev:
        return "NEUTRAL", "LOW"
        
    gap_seconds = (timestamp_curr - timestamp_prev).total_seconds()
    if gap_seconds > 1800: # 30 minutes
        logger.info(f"Time gap between snapshots is {gap_seconds}s (>1800s). Defaulting market state to NEUTRAL.")
        return "NEUTRAL", "LOW"

    # 2. Prevent division by zero
    if spot_prev <= 0:
        return "NEUTRAL", "LOW"

    # 3. Calculate percentage changes
    spot_change_pct = ((spot_curr - spot_prev) / spot_prev) * 100
    
    # Intraday cumulative volume change (volume always increases during trading session)
    vol_change_pct = 0.0
    if vol_prev > 0:
        vol_change_pct = ((vol_curr - vol_prev) / vol_prev) * 100

    oi_change_pct = 0.0
    if oi_prev > 0:
        oi_change_pct = ((oi_curr - oi_prev) / oi_prev) * 100

    # 4. Market Buildup Classification
    # LONG BUILD-UP: Price Up & OI Up
    if spot_change_pct > 0.0 and oi_change_pct > 0.0:
        if spot_change_pct >= 0.05 and oi_change_pct >= 2.0:
            return "LONG BUILD-UP", "HIGH"
        elif spot_change_pct >= 0.01 and oi_change_pct >= 0.5:
            return "LONG BUILD-UP", "MEDIUM"
        else:
            return "LONG BUILD-UP", "LOW"

    # SHORT BUILD-UP: Price Down & OI Up
    elif spot_change_pct < 0.0 and oi_change_pct > 0.0:
        if spot_change_pct <= -0.05 and oi_change_pct >= 2.0:
            return "SHORT BUILD-UP", "HIGH"
        elif spot_change_pct <= -0.01 and oi_change_pct >= 0.5:
            return "SHORT BUILD-UP", "MEDIUM"
        else:
            return "SHORT BUILD-UP", "LOW"

    # SHORT COVERING: Price Up & OI Down
    elif spot_change_pct > 0.0 and oi_change_pct < 0.0:
        if spot_change_pct >= 0.05 and oi_change_pct <= -2.0:
            return "SHORT COVERING", "HIGH"
        elif spot_change_pct >= 0.01 and oi_change_pct <= -0.5:
            return "SHORT COVERING", "MEDIUM"
        else:
            return "SHORT COVERING", "LOW"

    # LONG UNWINDING: Price Down & OI Down
    elif spot_change_pct < 0.0 and oi_change_pct < 0.0:
        if spot_change_pct <= -0.05 and oi_change_pct <= -2.0:
            return "LONG UNWINDING", "HIGH"
        elif spot_change_pct <= -0.01 and oi_change_pct <= -0.5:
            return "LONG UNWINDING", "MEDIUM"
        else:
            return "LONG UNWINDING", "LOW"

    return "NEUTRAL", "LOW"


def compute_strike_insights(
    snapshot: Any,
    strikes: List[Any]
) -> List[GeneratedInsight]:
    """
    Computes strike-level qualitative text insights in-memory without saving them.
    Supports generic snapshot and strike records.
    """
    if not strikes:
        return []

    insights_to_save = []
    
    # Calculate Total call/put values to find ratios & averages
    total_call_oi = sum(s.call_oi for s in strikes)
    total_put_oi = sum(s.put_oi for s in strikes)
    total_call_volume = sum(s.call_volume for s in strikes)
    total_put_volume = sum(s.put_volume for s in strikes)
    
    avg_call_volume = total_call_volume / len(strikes) if strikes else 1.0
    avg_put_volume = total_put_volume / len(strikes) if strikes else 1.0
    
    pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 0.0
    
    # 1. PCR Bias Check
    if pcr > 1.25:
        insights_to_save.append(GeneratedInsight(
            timestamp=snapshot.timestamp,
            symbol=snapshot.symbol,
            expiry_date=snapshot.expiry_date,
            category="BUILDUP",
            insight_text=f"Put OI dominance observed (PCR: {pcr:.2f}). Market positioning currently favors Put side.",
            confidence_level="HIGH",
            rule_version="v1.0"
        ))
    elif pcr < 0.8:
        insights_to_save.append(GeneratedInsight(
            timestamp=snapshot.timestamp,
            symbol=snapshot.symbol,
            expiry_date=snapshot.expiry_date,
            category="BUILDUP",
            insight_text=f"Call OI dominance observed (PCR: {pcr:.2f}). Market positioning currently favors Call side.",
            confidence_level="HIGH",
            rule_version="v1.0"
        ))

    # 2. Significant Strike additions
    # Find maximum change in Call OI and Put OI
    max_call_oi_add = max(strikes, key=lambda s: s.call_change_oi)
    max_put_oi_add = max(strikes, key=lambda s: s.put_change_oi)
    
    # Threshold for significant additions (e.g., > 10,000 for NIFTY, > 5,000 for BANKNIFTY)
    threshold = 10000 if snapshot.symbol == "NIFTY" else 5000
    
    if max_call_oi_add.call_change_oi > threshold:
        insights_to_save.append(GeneratedInsight(
            timestamp=snapshot.timestamp,
            symbol=snapshot.symbol,
            expiry_date=snapshot.expiry_date,
            category="BUILDUP",
            insight_text=f"Significant Call Open Interest addition of {max_call_oi_add.call_change_oi:,} observed at {max_call_oi_add.strike:.0f} strike. Interpreted as Call writing pressure.",
            confidence_level="HIGH",
            rule_version="v1.0"
        ))
        
    if max_put_oi_add.put_change_oi > threshold:
        insights_to_save.append(GeneratedInsight(
            timestamp=snapshot.timestamp,
            symbol=snapshot.symbol,
            expiry_date=snapshot.expiry_date,
            category="BUILDUP",
            insight_text=f"Significant Put Open Interest addition of {max_put_oi_add.put_change_oi:,} observed at {max_put_oi_add.strike:.0f} strike. Interpreted as Put writing support.",
            confidence_level="HIGH",
            rule_version="v1.0"
        ))

    # 3. Unusual Volume Triggers (Volume > 1.5x average volume)
    # Find strikes with highest volume relative to average
    for s in strikes:
        # Check call volume spike (only on strikes within +/- 5% of spot to filter noise)
        if s.strike > snapshot.spot_price * 0.95 and s.strike < snapshot.spot_price * 1.05:
            if s.call_volume > 2.0 * avg_call_volume and s.call_volume > 50000:
                insights_to_save.append(GeneratedInsight(
                    timestamp=snapshot.timestamp,
                    symbol=snapshot.symbol,
                    expiry_date=snapshot.expiry_date,
                    category="VOLATILITY",
                    insight_text=f"High traded volume of {s.call_volume:,} detected at {s.strike:.0f} Call contracts, indicating active positioning.",
                    confidence_level="MEDIUM",
                    rule_version="v1.0"
                ))
                break # Just output one volume warning to avoid cluttering the dashboard
                
    for s in strikes:
        if s.strike > snapshot.spot_price * 0.95 and s.strike < snapshot.spot_price * 1.05:
            if s.put_volume > 2.0 * avg_put_volume and s.put_volume > 50000:
                insights_to_save.append(GeneratedInsight(
                    timestamp=snapshot.timestamp,
                    symbol=snapshot.symbol,
                    expiry_date=snapshot.expiry_date,
                    category="VOLATILITY",
                    insight_text=f"High traded volume of {s.put_volume:,} detected at {s.strike:.0f} Put contracts, indicating active positioning.",
                    confidence_level="MEDIUM",
                    rule_version="v1.0"
                ))
                break

    return insights_to_save


def generate_strike_insights(
    db: Session,
    snapshot: OptionChainSnapshot,
    strikes: List[OptionChainStrike]
) -> List[GeneratedInsight]:
    """
    Generates strike-level qualitative text insights and saves them to the database.
    Only returns insights generated in this cycle.
    """
    insights_to_save = compute_strike_insights(snapshot, strikes)

    # Save to database
    if insights_to_save:
        db.add_all(insights_to_save)
        db.commit()
        logger.info(f"Generated and saved {len(insights_to_save)} qualitative insights for {snapshot.symbol}")
        
    return insights_to_save
