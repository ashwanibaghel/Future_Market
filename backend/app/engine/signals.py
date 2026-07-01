import logging
import json
import math
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.models import (
    OptionChainSnapshot,
    OptionChainStrike,
    AnalyticsSnapshot,
    MLFeatureSnapshot,
    TradingSignal,
    MarketRegime,
    TradeSession
)

logger = logging.getLogger(__name__)

def calculate_daily_options_vwap(db: Session, symbol: str, snapshot_timestamp: datetime) -> float:
    """
    Calculates options volume-weighted spot average for that calendar day:
    VWAP = Sum(Spot Price * Total Options Volume) / Sum(Total Options Volume)
    """
    start_of_day = datetime(snapshot_timestamp.year, snapshot_timestamp.month, snapshot_timestamp.day, 0, 0, 0)
    
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

def generate_trading_signal(db: Session, snapshot_id: int, version: str = "v2") -> TradingSignal:
    """
    Evaluates institutional-grade rule-based signals (v2 weighted scoring) for a snapshot.
    Saves and returns the TradingSignal record, skipping SENSEX when no strikes are present.
    """
    # 1. Fetch snapshot
    snapshot = db.query(OptionChainSnapshot).filter(OptionChainSnapshot.id == snapshot_id).first()
    if not snapshot:
        logger.warning(f"Snapshot with ID {snapshot_id} not found.")
        return None

    # Check if signal already exists for this snapshot and version
    existing = db.query(TradingSignal).filter(
        TradingSignal.snapshot_id == snapshot_id,
        TradingSignal.signal_version == version
    ).first()
    if existing:
        return existing

    # 2. Fetch strikes
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

    # Fetch MLFeatureSnapshot to get EMA20, EMA50, ATR, Avg IV
    ml_feature = db.query(MLFeatureSnapshot).filter(
        MLFeatureSnapshot.source_snapshot_id == snapshot_id,
        MLFeatureSnapshot.timeframe == "1m"
    ).first()

    # Fetch previous snapshots (up to 50) for rolling statistics - filtered by expiry_date!
    prev_snapshots = db.query(OptionChainSnapshot).filter(
        OptionChainSnapshot.symbol == snapshot.symbol,
        OptionChainSnapshot.expiry_date == snapshot.expiry_date,
        OptionChainSnapshot.collection_status == "SUCCESS",
        OptionChainSnapshot.id < snapshot_id
    ).order_by(OptionChainSnapshot.timestamp.desc()).limit(50).all()

    # --- 3. Compute Variables & Rolling Statistics ---
    current_spot = snapshot.spot_price
    pcr = curr_analytics.pcr
    market_state = curr_analytics.market_state
    strength = curr_analytics.strength

    # Fallbacks for EMAs and Volatilities
    ema20 = ml_feature.ema20 if (ml_feature and ml_feature.ema20 is not None) else current_spot
    ema50 = ml_feature.ema50 if (ml_feature and ml_feature.ema50 is not None) else current_spot
    atr_curr = ml_feature.atr if (ml_feature and ml_feature.atr is not None) else 1.0
    iv_curr = ml_feature.average_iv if (ml_feature and ml_feature.average_iv is not None) else 0.0

    # Calculate VWAP
    vwap = calculate_daily_options_vwap(db, snapshot.symbol, snapshot.timestamp)
    if vwap == 0.0:
        vwap = current_spot

    # Historical Rolling Averages (ATR & IV)
    prev_snapshot_ids = [s.id for s in prev_snapshots]
    if prev_snapshot_ids:
        prev_features = db.query(MLFeatureSnapshot).filter(
            MLFeatureSnapshot.source_snapshot_id.in_(prev_snapshot_ids),
            MLFeatureSnapshot.timeframe == "1m"
        ).all()
    else:
        prev_features = []

    prev_atrs = [f.atr for f in prev_features if f.atr is not None]
    avg_atr_50 = sum(prev_atrs) / len(prev_atrs) if prev_atrs else atr_curr
    if avg_atr_50 == 0.0:
        avg_atr_50 = 1.0
    vol_multiplier = atr_curr / avg_atr_50

    prev_ivs = [f.average_iv for f in prev_features if f.average_iv is not None]
    avg_iv_50 = sum(prev_ivs) / len(prev_ivs) if prev_ivs else iv_curr
    if avg_iv_50 == 0.0:
        avg_iv_50 = 1.0
    iv_multiplier = iv_curr / avg_iv_50

    # Version-based Parameter Calibration (A/B testing parallel execution)
    is_v25 = (version == "v2.5")
    
    # 1. Baseline Dynamic Threshold (Approved: 70 -> 60)
    baseline_threshold = 60.0
    
    # 2. Sensitivity Denominators
    vwap_denom = 0.75 if is_v25 else 1.5
    ema_denom = 0.0005 if is_v25 else 0.001
    price_denom = 0.0005 if is_v25 else 0.001
    pcr_denom = 0.05 if is_v25 else 0.10
    oi_denom_factor = 1.5 if is_v25 else 2.0
    greeks_denom = 0.05 if is_v25 else 0.10

    # Dynamic Volatility-Adjusted Threshold (ATR + IV)
    vol_factor = (vol_multiplier - 1.0) * 5.0 + (iv_multiplier - 1.0) * 5.0
    dynamic_threshold = baseline_threshold + min(15.0, max(-10.0, vol_factor))

    # Rolling OI changes
    curr_total_oi = sum((s.call_oi + s.put_oi) for s in strikes)
    prev_total_ois = []
    for p_snap in prev_snapshots:
        p_strikes = db.query(OptionChainStrike).filter(OptionChainStrike.snapshot_id == p_snap.id).all()
        prev_total_ois.append(sum((s.call_oi + s.put_oi) for s in p_strikes))

    oi_abs_pct_changes = []
    for i in range(len(prev_total_ois) - 1):
        c_oi = prev_total_ois[i]
        p_oi = prev_total_ois[i+1]
        if p_oi > 0:
            oi_abs_pct_changes.append(abs(c_oi - p_oi) / p_oi)
    avg_change_oi = sum(oi_abs_pct_changes) / len(oi_abs_pct_changes) if oi_abs_pct_changes else 0.01
    if avg_change_oi == 0.0:
        avg_change_oi = 0.01

    # Current OI change
    prev_total_oi = prev_total_ois[0] if prev_total_ois else curr_total_oi
    delta_oi = (curr_total_oi - prev_total_oi) / prev_total_oi if prev_total_oi > 0 else 0.0

    # OI Acceleration
    prev_delta_oi = 0.0
    if len(prev_total_ois) > 1:
        prev_delta_oi = (prev_total_ois[0] - prev_total_ois[1]) / prev_total_ois[1] if prev_total_ois[1] > 0 else 0.0
    oi_acceleration = delta_oi - prev_delta_oi

    # Volume Z-Score
    curr_total_vol = sum((s.call_volume + s.put_volume) for s in strikes)
    prev_total_vols = []
    for p_snap in prev_snapshots[:20]:
        p_strikes = db.query(OptionChainStrike).filter(OptionChainStrike.snapshot_id == p_snap.id).all()
        prev_total_vols.append(sum((s.call_volume + s.put_volume) for s in p_strikes))

    if prev_total_vols:
        vol_mean = sum(prev_total_vols) / len(prev_total_vols)
        vol_variance = sum((x - vol_mean) ** 2 for x in prev_total_vols) / len(prev_total_vols)
        vol_std = math.sqrt(vol_variance)
    else:
        vol_mean = curr_total_vol
        vol_std = 0.0
    volume_z_score = (curr_total_vol - vol_mean) / vol_std if vol_std > 0 else 0.0

    # Greeks Bias (Delta ATM strike) - using closest ATM strike to avoid symmetric cancellation
    sorted_strikes = sorted(strikes, key=lambda s: abs(s.strike - current_spot))
    closest_strike = sorted_strikes[0] if sorted_strikes else None
    close_strikes = sorted_strikes[:5]
    
    if closest_strike and (closest_strike.call_delta != 0.0 or closest_strike.put_delta != 0.0):
        net_delta = closest_strike.call_delta + closest_strike.put_delta
        net_gamma = closest_strike.call_gamma + closest_strike.put_gamma
        greeks_available = True
    else:
        net_delta = 0.0
        net_gamma = 0.0
        greeks_available = False

    # --- 4. Evaluate Audited Rules (Bullish & Bearish) ---
    bullish_reasons = {}
    bearish_reasons = {}

    # Rule 1: Market State Sentiment Regime (Max 15 pts)
    strength_mult = 1.0 if strength == "HIGH" else (0.7 if strength == "MEDIUM" else 0.3)
    bull_state_class = 1.0 if market_state == "LONG BUILD-UP" else (0.7 if market_state == "SHORT COVERING" else 0.0)
    bear_state_class = 1.0 if market_state == "SHORT BUILD-UP" else (0.7 if market_state == "LONG UNWINDING" else 0.0)
    bull_r1 = 15.0 * bull_state_class * strength_mult
    bear_r1 = 15.0 * bear_state_class * strength_mult
    bullish_reasons["Market State"] = {"raw": market_state, "normalized": bull_state_class * strength_mult, "weight": 15, "contribution": round(bull_r1, 2)}
    bearish_reasons["Market State"] = {"raw": market_state, "normalized": bear_state_class * strength_mult, "weight": 15, "contribution": round(bear_r1, 2)}

    # Rule 2: VWAP Distance (ATR-Scaled) (Max 15 pts) - Calibrated dynamically
    vwap_dist = current_spot - vwap
    dist_in_atr = abs(vwap_dist) / atr_curr if atr_curr > 0 else 0.0
    norm_dist = min(1.0, dist_in_atr / vwap_denom)
    bull_r2 = norm_dist * 15.0 if vwap_dist > 0 else 0.0
    bear_r2 = norm_dist * 15.0 if vwap_dist < 0 else 0.0
    bullish_reasons["VWAP Distance"] = {"raw": round(vwap_dist, 2), "normalized": norm_dist if vwap_dist > 0 else 0.0, "weight": 15, "contribution": round(bull_r2, 2)}
    bearish_reasons["VWAP Distance"] = {"raw": round(vwap_dist, 2), "normalized": norm_dist if vwap_dist < 0 else 0.0, "weight": 15, "contribution": round(bear_r2, 2)}

    # Rule 3: EMA Trends & Crosses (Max 15 pts) - Calibrated dynamically
    ema20_dist = (current_spot - ema20) / ema20 if ema20 > 0 else 0.0
    norm_ema20_dist = min(1.0, abs(ema20_dist) / ema_denom)
    bull_ema20_pts = norm_ema20_dist * 5.0 if ema20_dist > 0 else 0.0
    bear_ema20_pts = norm_ema20_dist * 5.0 if ema20_dist < 0 else 0.0
    bull_ema_cross = 10.0 if ema20 > ema50 else 0.0
    bear_ema_cross = 10.0 if ema20 < ema50 else 0.0
    bull_r3 = bull_ema20_pts + bull_ema_cross
    bear_r3 = bear_ema20_pts + bear_ema_cross
    bullish_reasons["EMA Trends"] = {"raw": f"spot_ema20_diff={round(current_spot - ema20, 2)}, ema20_gt_ema50={ema20 > ema50}", "normalized": (bull_ema20_pts/5.0 * 0.33 + bull_ema_cross/10.0 * 0.67), "weight": 15, "contribution": round(bull_r3, 2)}
    bearish_reasons["EMA Trends"] = {"raw": f"spot_ema20_diff={round(current_spot - ema20, 2)}, ema20_lt_ema50={ema20 < ema50}", "normalized": (bear_ema20_pts/5.0 * 0.33 + bear_ema_cross/10.0 * 0.67), "weight": 15, "contribution": round(bear_r3, 2)}

    # Rule 4: OI Change (Rolling Percentile) (Max 15 pts) - Calibrated dynamically
    norm_oi = min(1.0, delta_oi / (oi_denom_factor * avg_change_oi)) if delta_oi > 0 else 0.0
    bull_r4 = norm_oi * 15.0 if delta_oi > 0 else 0.0
    bear_r4 = norm_oi * 15.0 if delta_oi > 0 else 0.0
    bullish_reasons["OI Change"] = {"raw": f"delta_oi={round(delta_oi*100, 3)}%, accel={round(oi_acceleration*100, 3)}%", "normalized": norm_oi if delta_oi > 0 else 0.0, "weight": 15, "contribution": round(bull_r4, 2)}
    bearish_reasons["OI Change"] = {"raw": f"delta_oi={round(delta_oi*100, 3)}%, accel={round(oi_acceleration*100, 3)}%", "normalized": norm_oi if delta_oi > 0 else 0.0, "weight": 15, "contribution": round(bear_r4, 2)}

    # Rule 5: Options Volume & Spike (Max 15 pts)
    call_vol = sum(s.call_volume for s in strikes)
    put_vol = sum(s.put_volume for s in strikes)
    pcr_vol = put_vol / call_vol if call_vol > 0 else 1.0
    bull_pcr_vol_pts = 10.0 if pcr_vol > 1.5 else (5.0 if pcr_vol > 1.2 else (3.0 if pcr_vol > 1.0 else 0.0))
    bear_pcr_vol_pts = 10.0 if pcr_vol < 0.6 else (5.0 if pcr_vol < 0.8 else (3.0 if pcr_vol < 1.0 else 0.0))
    vol_spike_pts = 5.0 if volume_z_score > 2.0 else (3.0 if volume_z_score > 1.0 else 0.0)
    bull_r5 = bull_pcr_vol_pts + vol_spike_pts
    bear_r5 = bear_pcr_vol_pts + vol_spike_pts
    bullish_reasons["Options Volume"] = {"raw": f"pcr_vol={round(pcr_vol, 2)}, z_score={round(volume_z_score, 2)}", "normalized": (bull_pcr_vol_pts/10.0 * 0.67 + vol_spike_pts/5.0 * 0.33), "weight": 15, "contribution": round(bull_r5, 2)}
    bearish_reasons["Options Volume"] = {"raw": f"pcr_vol={round(pcr_vol, 2)}, z_score={round(volume_z_score, 2)}", "normalized": (bear_pcr_vol_pts/10.0 * 0.67 + vol_spike_pts/5.0 * 0.33), "weight": 15, "contribution": round(bear_r5, 2)}

    # Rule 6: PCR Trend & Magnitude (Max 10 pts)
    pcr_prev = pcr
    if prev_snapshots:
        prev_analytics = db.query(AnalyticsSnapshot).filter(AnalyticsSnapshot.source_snapshot_id == prev_snapshots[0].id).first()
        if prev_analytics:
            pcr_prev = prev_analytics.pcr
    delta_pcr = pcr - pcr_prev
    norm_pcr = min(1.0, abs(delta_pcr) / pcr_denom)
    bull_r6 = norm_pcr * 10.0 if delta_pcr > 0 else 0.0
    bear_r6 = norm_pcr * 10.0 if delta_pcr < 0 else 0.0
    bullish_reasons["PCR Trend"] = {"raw": round(delta_pcr, 4), "normalized": norm_pcr if delta_pcr > 0 else 0.0, "weight": 10, "contribution": round(bull_r6, 2)}
    bearish_reasons["PCR Trend"] = {"raw": round(delta_pcr, 4), "normalized": norm_pcr if delta_pcr < 0 else 0.0, "weight": 10, "contribution": round(bear_r6, 2)}

    # Rule 7: Price Momentum (Max 10 pts) - Calibrated dynamically
    spot_prev = prev_snapshots[0].spot_price if prev_snapshots else current_spot
    delta_spot = (current_spot - spot_prev) / spot_prev if spot_prev > 0 else 0.0
    norm_spot = min(1.0, abs(delta_spot) / price_denom)
    bull_r7 = norm_spot * 10.0 if delta_spot > 0 else 0.0
    bear_r7 = norm_spot * 10.0 if delta_spot < 0 else 0.0
    bullish_reasons["Price Momentum"] = {"raw": f"{round(delta_spot*100, 3)}%", "normalized": norm_spot if delta_spot > 0 else 0.0, "weight": 10, "contribution": round(bull_r7, 2)}
    bearish_reasons["Price Momentum"] = {"raw": f"{round(delta_spot*100, 3)}%", "normalized": norm_spot if delta_spot < 0 else 0.0, "weight": 10, "contribution": round(bear_r7, 2)}

    # Rule 8: Option Greeks (Max 10 pts) & Compiled Scores
    if greeks_available:
        norm_greeks = min(1.0, abs(net_delta) / greeks_denom)
        bull_r8 = norm_greeks * 10.0 if net_delta > 0 else 0.0
        bear_r8 = norm_greeks * 10.0 if net_delta < 0 else 0.0
        bullish_reasons["Greeks"] = {"raw": f"net_delta={round(net_delta, 3)}, net_gamma={round(net_gamma, 5)}", "normalized": norm_greeks if net_delta > 0 else 0.0, "weight": 10, "contribution": round(bull_r8, 2)}
        bearish_reasons["Greeks"] = {"raw": f"net_delta={round(net_delta, 3)}, net_gamma={round(net_gamma, 5)}", "normalized": norm_greeks if net_delta < 0 else 0.0, "weight": 10, "contribution": round(bear_r8, 2)}

        bullish_score = round(bull_r1 + bull_r2 + bull_r3 + bull_r4 + bull_r5 + bull_r6 + bull_r7 + bull_r8, 2)
        bearish_score = round(bear_r1 + bear_r2 + bear_r3 + bear_r4 + bear_r5 + bear_r6 + bear_r7 + bear_r8, 2)
    else:
        # Exclude Greeks from calculation and scale the 90 points raw score to a 100 point scale
        raw_bull = bull_r1 + bull_r2 + bull_r3 + bull_r4 + bull_r5 + bull_r6 + bull_r7
        raw_bear = bear_r1 + bear_r2 + bear_r3 + bear_r4 + bear_r5 + bear_r6 + bear_r7
        bullish_score = round((raw_bull / 90.0) * 100.0, 2)
        bearish_score = round((raw_bear / 90.0) * 100.0, 2)

        bullish_reasons["Greeks"] = {"raw": "N/A (Missing Greeks Fallback applied)", "normalized": 0.0, "weight": 0, "contribution": 0.0}
        bearish_reasons["Greeks"] = {"raw": "N/A (Missing Greeks Fallback applied)", "normalized": 0.0, "weight": 0, "contribution": 0.0}

    # --- 5. Compile Final V2 Metrics ---
    decision_margin = round(abs(bullish_score - bearish_score), 2)
    confidence_ratio = round((max(bullish_score, bearish_score) / (bullish_score + bearish_score) * 100), 2) if (bullish_score + bearish_score) > 0.0 else 0.0

    # Fetch previous signals for persistence - filtered by expiry_date & version!
    prev_signals = db.query(TradingSignal).filter(
        TradingSignal.symbol == snapshot.symbol,
        TradingSignal.expiry_date == snapshot.expiry_date,
        TradingSignal.signal_version == version,
        TradingSignal.snapshot_id < snapshot_id
    ).order_by(TradingSignal.snapshot_id.desc()).limit(1).all()

    prev_bullish = [s.bullish_score for s in prev_signals if s.bullish_score is not None]
    prev_bearish = [s.bearish_score for s in prev_signals if s.bearish_score is not None]

    # 2-Minute score rolling average persistence filter (current + 1 previous snapshot)
    bull_2m_avg = round((bullish_score + sum(prev_bullish)) / (1 + len(prev_bullish)), 2)
    bear_2m_avg = round((bearish_score + sum(prev_bearish)) / (1 + len(prev_bearish)), 2)

    # Determine final published signal
    if bull_2m_avg >= dynamic_threshold:
        signal_type = "BUY_CALL"
    elif bear_2m_avg >= dynamic_threshold:
        signal_type = "BUY_PUT"
    else:
        signal_type = "NO_TRADE"

    # Raw signal without rolling persistence
    if bullish_score >= dynamic_threshold:
        raw_signal = "BUY_CALL"
    elif bearish_score >= dynamic_threshold:
        raw_signal = "BUY_PUT"
    else:
        raw_signal = "NO_TRADE"

    # Expected Strength Classification (based on dynamic_threshold)
    primary_score = bullish_score if bullish_score >= bearish_score else bearish_score
    primary_reasons = bullish_reasons if bullish_score >= bearish_score else bearish_reasons

    if signal_type in ["BUY_CALL", "BUY_PUT"]:
        if primary_score >= 80.0:
            expected_strength = "Exceptional Setup"
        else:
            expected_strength = "Strong Signal"
    else:
        if primary_score >= 50.0:
            expected_strength = "Almost Ready"
        elif primary_score >= 35.0:
            expected_strength = "Developing Setup"
        else:
            expected_strength = "Weak Setup"

    # Closest Failed Rule Logic
    closest_failed_rule = None
    if signal_type == "NO_TRADE":
        failed_candidates = []
        for rule_name, data in primary_reasons.items():
            weight = data.get("weight", 0)
            contrib = data.get("contribution", 0.0)
            if weight > 0 and contrib < weight:
                discrepancy = weight - contrib
                failed_candidates.append((rule_name, discrepancy))
        
        if failed_candidates:
            failed_candidates.sort(key=lambda x: x[1], reverse=True)
            name_mapping = {
                "Market State": "Market State Regime",
                "VWAP Distance": "VWAP Confirmation",
                "EMA Trends": "EMA Trend Confirmation",
                "OI Change": "OI Accumulation",
                "Options Volume": "Options Volume Bias",
                "PCR Trend": "PCR Trend Bias",
                "Price Momentum": "Price Momentum",
                "Greeks": "Greeks Bias"
            }
            raw_rule_name = failed_candidates[0][0]
            closest_failed_rule = name_mapping.get(raw_rule_name, raw_rule_name)

    # Explainability output JSON mapping rules and actual values
    reasons_v2 = bullish_reasons if bull_2m_avg >= bear_2m_avg else bearish_reasons
    
    # Feature Importance (Top Contributors)
    contribs = [{"rule": k, "contribution_pct": round(v["contribution"], 2)} for k, v in reasons_v2.items()]
    top_contribs = sorted(contribs, key=lambda x: x["contribution_pct"], reverse=True)[:3]

    # Calculate Data Quality Score
    data_quality_score = 100
    if all(s.call_delta == 0.0 and s.put_delta == 0.0 for s in close_strikes):
        data_quality_score -= 20
    if pcr == 0.0:
        data_quality_score -= 15
    if curr_total_vol == 0:
        data_quality_score -= 15
    if atr_curr <= 1.0:
        data_quality_score -= 10

    # Determine Lifecycle State
    prev_signal = prev_signals[0] if prev_signals else None
    if not prev_signal or prev_signal.signal_type == "NO_TRADE":
        lifecycle_state = "CREATED" if signal_type != "NO_TRADE" else "CREATED"
    else:
        if signal_type == "NO_TRADE":
            lifecycle_state = "CANCELLED"
        elif signal_type == prev_signal.signal_type:
            curr_score = bullish_score if signal_type == "BUY_CALL" else bearish_score
            prev_score = prev_signal.bullish_score if signal_type == "BUY_CALL" else prev_signal.bearish_score
            if curr_score > prev_score + 2.0:
                lifecycle_state = "STRENGTHENED"
            elif curr_score < prev_score - 2.0:
                lifecycle_state = "WEAKENED"
            else:
                lifecycle_state = prev_signal.lifecycle_state
        else:
            lifecycle_state = "CREATED"

    # Greeks bias details inside rich inputs log
    signal_inputs_dict = {
        "spot": current_spot,
        "pcr": pcr,
        "vwap": vwap,
        "ema20": ema20,
        "ema50": ema50,
        "atr": atr_curr,
        "average_iv": iv_curr,
        "volatility_multiplier": vol_multiplier,
        "iv_multiplier": iv_multiplier,
        "oi_acceleration": oi_acceleration,
        "volume_z_score": volume_z_score,
        "net_delta_bias": net_delta,
        "market_state": market_state,
        "strength": strength
    }

    # ATM Strike Selection
    suggested_strike = None
    strike_selection_reason = None
    if signal_type != "NO_TRADE":
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
        matched_conditions=int(round(bullish_score if signal_type == "BUY_CALL" else (bearish_score if signal_type == "BUY_PUT" else max(bullish_score, bearish_score)))),
        total_conditions=100,
        reasons=json.dumps(reasons_v2),
        signal_inputs=json.dumps(signal_inputs_dict),
        market_state=market_state,
        signal_version=version,
        was_executed=False,
        status="PENDING",
        
        # Sprint 16 V2 DB Columns
        bullish_score=bullish_score,
        bearish_score=bearish_score,
        decision_margin=decision_margin,
        confidence_ratio=confidence_ratio,
        dynamic_threshold=round(dynamic_threshold, 2),
        raw_signal=raw_signal,
        volume_z_score=volume_z_score,
        feature_version="v2.0",
        data_quality_score=data_quality_score,
        top_contributors=json.dumps(top_contribs),
        lifecycle_state=lifecycle_state,
        expected_strength=expected_strength,
        closest_failed_rule=closest_failed_rule
    )

    db.add(trading_signal)
    db.commit()
    db.refresh(trading_signal)

    logger.info(f"Generated V2 TradingSignal ID {trading_signal.id} ({signal_type}) for {snapshot.symbol} at {snapshot.timestamp}")

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

    # --- Regime Detection & Classification (Table population) ---
    try:
        trend_regime = "RANGING"
        vol_regime = "LOW"
        if market_state in ["LONG BUILD-UP", "SHORT BUILD-UP"] and strength == "HIGH":
            trend_regime = "TRENDING"
        elif abs(current_spot - ema50) > 2.5 * atr_curr:
            trend_regime = "TRENDING"
            
        if vol_multiplier > 1.2 or iv_multiplier > 1.2:
            vol_regime = "HIGH"
            
        regime_confidence = 80.0 if trend_regime == "TRENDING" and vol_regime == "HIGH" else 65.0
        session_phase = ml_feature.session_phase if ml_feature else "MIDDAY"
        
        market_regime = MarketRegime(
            timestamp=snapshot.timestamp,
            symbol=snapshot.symbol,
            trend=trend_regime,
            volatility=vol_regime,
            session_phase=session_phase,
            regime_confidence=regime_confidence
        )
        db.add(market_regime)
        db.commit()
        logger.info(f"Logged MarketRegime ({trend_regime}, {vol_regime}) for {snapshot.symbol}")
    except Exception as re_err:
        logger.error(f"Failed to log MarketRegime: {str(re_err)}")

    return trading_signal
