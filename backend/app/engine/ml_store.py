import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.db.models import (
    OptionChainSnapshot, OptionChainStrike, AnalyticsSnapshot,
    OptionChainSnapshot5m, OptionChainStrike5m, AnalyticsSnapshot5m,
    OptionChainSnapshot15m, OptionChainStrike15m, AnalyticsSnapshot15m,
    RawProviderResponse, MLFeatureSnapshot
)
from app.config import settings

logger = logging.getLogger(__name__)

def is_last_thursday(dt: datetime) -> bool:
    """
    Checks if a given date is the last Thursday of its calendar month.
    """
    # Thursday is weekday 3 (Mon=0, Tue=1, Wed=2, Thu=3)
    if dt.weekday() != 3:
        return False
    # If adding 7 days shifts the month, it is the last Thursday
    return (dt + timedelta(days=7)).month != dt.month

def calculate_expiry_type(expiry_date_str: str) -> str:
    """
    Determines if the expiry date is WEEKLY or MONTHLY based on last-Thursday logic.
    Accepts expiry_date_str in format like '25-Jun-2026' or '2026-06-25'.
    """
    try:
        try:
            dt = datetime.strptime(expiry_date_str, "%d-%b-%Y")
        except ValueError:
            dt = datetime.strptime(expiry_date_str, "%Y-%m-%d")
        
        # If adding 7 days changes the month, it's MONTHLY, else WEEKLY
        next_week = dt + timedelta(days=7)
        if next_week.month != dt.month:
            return "MONTHLY"
        return "WEEKLY"
    except Exception as e:
        logger.warning(f"Error parsing expiry date '{expiry_date_str}': {str(e)}")
        return "WEEKLY"

def calculate_day_type(now_dt: datetime, expiry_date_str: str, expiry_type: str) -> str:
    """
    Returns day type: EXPIRY_DAY, PRE_EXPIRY, NORMAL, MONTHLY_EXPIRY.
    """
    try:
        try:
            expiry_dt = datetime.strptime(expiry_date_str, "%d-%b-%Y")
        except ValueError:
            expiry_dt = datetime.strptime(expiry_date_str, "%Y-%m-%d")
        
        now_date = now_dt.date()
        expiry_date = expiry_dt.date()
        
        if now_date == expiry_date:
            return "MONTHLY_EXPIRY" if expiry_type == "MONTHLY" else "EXPIRY_DAY"
        elif now_date + timedelta(days=1) == expiry_date:
            return "PRE_EXPIRY"
        else:
            return "NORMAL"
    except Exception as e:
        logger.warning(f"Error calculating day type for {expiry_date_str}: {str(e)}")
        return "NORMAL"

def get_exchange_timestamp(db: Session, symbol: str, save_time: datetime) -> datetime:
    """
    Retrieves the exchange timestamp from the latest RawProviderResponse.
    Falls back to save_time if parsing fails.
    """
    try:
        # Get raw response nearest to save_time
        raw_resp = db.query(RawProviderResponse).filter(
            RawProviderResponse.symbol == symbol,
            RawProviderResponse.timestamp <= save_time + timedelta(seconds=10)
        ).order_by(RawProviderResponse.timestamp.desc()).first()
        
        if raw_resp and raw_resp.payload_json:
            data = json.loads(raw_resp.payload_json)
            ts_str = data.get("timestamp") # Format: "19-Jun-2026 15:30:00"
            if ts_str:
                exchange_dt = datetime.strptime(ts_str, "%d-%b-%Y %H:%M:%S")
                # Convert IST to UTC (subtract 5h 30m)
                exchange_utc = exchange_dt - timedelta(hours=5, minutes=30)
                return exchange_utc
    except Exception as e:
        logger.warning(f"Failed to extract exchange timestamp: {str(e)}")
    return save_time

def calculate_ema_and_atr(
    db: Session, symbol: str, timeframe: str, current_spot: float, prev_spot: float
) -> Tuple[float, float, float]:
    """
    Calculates EMA20, EMA50, and ATR (using spot changes as proxy) recursively
    based on the previous feature snapshots.
    """
    # Fetch the latest MLFeatureSnapshot for this symbol & timeframe
    prev_feature = db.query(MLFeatureSnapshot).filter(
        MLFeatureSnapshot.symbol == symbol,
        MLFeatureSnapshot.timeframe == timeframe
    ).order_by(MLFeatureSnapshot.timestamp.desc()).first()
    
    if prev_feature:
        prev_ema20 = prev_feature.ema20
        prev_ema50 = prev_feature.ema50
        prev_atr = prev_feature.atr
    else:
        prev_ema20, prev_ema50, prev_atr = None, None, None

    # True range proxy = absolute price change
    tr = abs(current_spot - prev_spot) if prev_spot is not None else 0.0

    # Calculate EMA20
    if prev_ema20 is not None:
        ema20 = current_spot * (2.0 / 21.0) + prev_ema20 * (19.0 / 21.0)
    else:
        ema20 = current_spot
        
    # Calculate EMA50
    if prev_ema50 is not None:
        ema50 = current_spot * (2.0 / 51.0) + prev_ema50 * (49.0 / 51.0)
    else:
        ema50 = current_spot
        
    # Calculate ATR (14-period EMA of True Range)
    if prev_atr is not None:
        atr = tr * (2.0 / 15.0) + prev_atr * (13.0 / 15.0)
    else:
        atr = tr if tr > 0 else 1.0 # default to 1.0 to avoid divide by zero

    return ema20, ema50, atr

def capture_ml_features(db: Session, snapshot_id: int, timeframe: str = "1m") -> bool:
    """
    Pulls data from a timeframe's snapshot/analytics and saves a new record in ml_feature_snapshots.
    """
    logger.info(f"Capturing ML features for {timeframe} snapshot ID {snapshot_id}...")
    try:
        # 1. Map classes
        if timeframe == "1m":
            snap_cls, strike_cls, analytics_cls = OptionChainSnapshot, OptionChainStrike, AnalyticsSnapshot
        elif timeframe == "5m":
            snap_cls, strike_cls, analytics_cls = OptionChainSnapshot5m, OptionChainStrike5m, AnalyticsSnapshot5m
        elif timeframe == "15m":
            snap_cls, strike_cls, analytics_cls = OptionChainSnapshot15m, OptionChainStrike15m, AnalyticsSnapshot15m
        else:
            raise ValueError(f"Invalid timeframe {timeframe}")

        # 2. Fetch data
        snapshot = db.query(snap_cls).filter(snap_cls.id == snapshot_id).first()
        if not snapshot:
            logger.warning(f"Snapshot ID {snapshot_id} not found in {timeframe} table.")
            return False

        analytics = db.query(analytics_cls).filter(analytics_cls.source_snapshot_id == snapshot_id).first()
        strikes = db.query(strike_cls).filter(strike_cls.snapshot_id == snapshot_id).all()

        symbol = snapshot.symbol
        expiry_date = snapshot.expiry_date
        spot = snapshot.spot_price
        timestamp = snapshot.timestamp

        # 3. Handle previous spot for ATR/EMA
        prev_snap = db.query(snap_cls).filter(
            snap_cls.symbol == symbol,
            snap_cls.expiry_date == expiry_date,
            snap_cls.timestamp < timestamp
        ).order_by(snap_cls.timestamp.desc()).first()
        prev_spot = prev_snap.spot_price if prev_snap else None

        # 4. Compute temporal/session/expiry parameters
        market_date = timestamp.strftime("%Y-%m-%d")
        
        try:
            try:
                expiry_dt = datetime.strptime(expiry_date, "%d-%b-%Y")
            except ValueError:
                expiry_dt = datetime.strptime(expiry_date, "%Y-%m-%d")
            days_to_expiry = (expiry_dt.date() - timestamp.date()).days
        except Exception:
            days_to_expiry = 0

        # Session minutes
        market_open = timestamp.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = timestamp.replace(hour=15, minute=30, second=0, microsecond=0)
        if timestamp < market_open:
            minutes_from_open = 0
        elif timestamp > market_close:
            minutes_from_open = 375
        else:
            minutes_from_open = int((timestamp - market_open).total_seconds() / 60)
        minutes_to_close = max(0, 375 - minutes_from_open)

        if minutes_from_open <= 45:
            session_phase = "OPENING"
        elif minutes_to_close <= 45:
            session_phase = "CLOSING"
        else:
            session_phase = "MIDDAY"

        expiry_type = calculate_expiry_type(expiry_date)
        day_type = calculate_day_type(timestamp, expiry_date, expiry_type)

        # 5. Extract Sentiment Metrics
        pcr = analytics.pcr if analytics else None
        
        # PCR velocity against previous snapshot
        prev_feat = db.query(MLFeatureSnapshot).filter(
            MLFeatureSnapshot.symbol == symbol,
            MLFeatureSnapshot.expiry_date == expiry_date,
            MLFeatureSnapshot.timeframe == timeframe
        ).order_by(MLFeatureSnapshot.timestamp.desc()).first()
        
        pcr_velocity = 0.0
        if prev_feat and prev_feat.pcr is not None and pcr is not None:
            pcr_velocity = pcr - prev_feat.pcr

        total_call_oi = sum(s.call_oi for s in strikes) if strikes else 0
        total_put_oi = sum(s.put_oi for s in strikes) if strikes else 0
        oi_imbalance = total_put_oi / max(1.0, total_call_oi)

        call_change_oi = sum(s.call_change_oi for s in strikes) if strikes else 0
        put_change_oi = sum(s.put_change_oi for s in strikes) if strikes else 0
        order_flow = float(put_change_oi - call_change_oi)

        total_strikes = len(strikes)
        active_iv_strikes = sum(1 for s in strikes if s.call_iv > 0 or s.put_iv > 0)
        
        average_iv = 0.0
        if total_strikes > 0:
            average_iv = sum(s.call_iv + s.put_iv for s in strikes) / (total_strikes * 2)

        iv_change = 0.0
        if prev_feat and prev_feat.average_iv and prev_feat.average_iv > 0:
            iv_change = ((average_iv - prev_feat.average_iv) / prev_feat.average_iv) * 100
        elif analytics:
            iv_change = analytics.iv_change or 0.0

        # 6. Extract Levels & Boundary Metrics
        support = analytics.support if analytics else None
        sec_support = analytics.secondary_support if analytics else None
        resistance = analytics.resistance if analytics else None
        sec_resistance = analytics.secondary_resistance if analytics else None

        distance_to_s1 = spot - support if support is not None else None
        distance_to_s2 = spot - sec_support if sec_support is not None else None
        distance_to_r1 = resistance - spot if resistance is not None else None
        distance_to_r2 = sec_resistance - spot if sec_resistance is not None else None

        distance_to_s1_pct = ((spot - support) / spot * 100.0) if spot > 0 and support is not None else None
        distance_to_r1_pct = ((resistance - spot) / spot * 100.0) if spot > 0 and resistance is not None else None
        sr_compression = resistance - support if resistance is not None and support is not None else None

        support_strength = analytics.support_strength if analytics else None
        resistance_strength = analytics.resistance_strength if analytics else None

        # 7. Pre-encode Market State
        market_state = analytics.market_state if analytics else "NEUTRAL"
        state_str = (market_state or "").upper().replace("-", " ").strip()
        if "LONG BUILD UP" in state_str or "LONG BUILD-UP" in state_str:
            market_state_id = 1
        elif "SHORT BUILD UP" in state_str or "SHORT BUILD-UP" in state_str:
            market_state_id = 2
        elif "SHORT COVERING" in state_str:
            market_state_id = 3
        elif "LONG UNWINDING" in state_str:
            market_state_id = 4
        else:
            market_state_id = 0

        strength = analytics.strength if analytics else "LOW"
        strength_str = (strength or "").upper().strip()
        if strength_str == "LOW":
            strength_score = 1
        elif strength_str == "MEDIUM":
            strength_score = 2
        elif strength_str == "HIGH":
            strength_score = 3
        else:
            strength_score = 1

        # 8. Compute indicators and trend
        ema20, ema50, atr = calculate_ema_and_atr(db, symbol, timeframe, spot, prev_spot)
        
        # Calculate trend using the EMA20, EMA50, ATR parameters
        threshold = 0.1 * atr
        if ema20 > ema50 + threshold:
            regime_trend = "UPTREND"
        elif ema20 < ema50 - threshold:
            regime_trend = "DOWNTREND"
        else:
            regime_trend = "RANGE"

        # 9. Compute data quality score (0-100)
        data_quality_score = 100
        if total_strikes == 0:
            data_quality_score = 0
        else:
            # Penalty for low number of strikes
            if total_strikes < 10:
                data_quality_score -= 20
            # Penalty for missing IVs
            if active_iv_strikes == 0:
                data_quality_score -= 40
            elif active_iv_strikes < (total_strikes / 2):
                data_quality_score -= 20
            # Penalty for missing PCR
            if pcr is None or pcr == 0.0:
                data_quality_score -= 20
            # Penalty for missing S/R levels
            if support is None or resistance is None or support == 0.0 or resistance == 0.0:
                data_quality_score -= 20
        data_quality_score = max(0, min(100, data_quality_score))

        # 10. Compute snapshot age (latency)
        exchange_time = get_exchange_timestamp(db, symbol, timestamp)
        snapshot_age_seconds = float((timestamp - exchange_time).total_seconds())

        # 11. Feature flags JSON map
        flags = {
            "has_iv": active_iv_strikes > 0,
            "has_sr": (support is not None and support > 0 and resistance is not None and resistance > 0),
            "has_pcr": pcr is not None and pcr > 0,
            "has_order_flow": order_flow is not None
        }
        feature_flags = json.dumps(flags)

        # 12. Create feature snapshot record
        feat_record = MLFeatureSnapshot(
            timestamp=timestamp,
            market_date=market_date,
            timeframe=timeframe,
            symbol=symbol,
            expiry_date=expiry_date,
            expiry_type=expiry_type,
            source_snapshot_id=snapshot_id,
            days_to_expiry=days_to_expiry,
            minutes_from_open=minutes_from_open,
            minutes_to_close=minutes_to_close,
            session_phase=session_phase,
            day_type=day_type,
            data_quality_score=data_quality_score,
            snapshot_age_seconds=snapshot_age_seconds,
            feature_flags=feature_flags,
            feature_schema_version="v1",
            pcr=pcr,
            pcr_velocity=pcr_velocity,
            oi_imbalance=oi_imbalance,
            average_iv=average_iv,
            iv_change=iv_change,
            total_call_oi=total_call_oi,
            total_put_oi=total_put_oi,
            call_change_oi=call_change_oi,
            put_change_oi=put_change_oi,
            distance_to_s1=distance_to_s1,
            distance_to_s2=distance_to_s2,
            distance_to_r1=distance_to_r1,
            distance_to_r2=distance_to_r2,
            distance_to_s1_pct=distance_to_s1_pct,
            distance_to_r1_pct=distance_to_r1_pct,
            sr_compression=sr_compression,
            support_strength=support_strength,
            resistance_strength=resistance_strength,
            market_state=market_state,
            market_state_id=market_state_id,
            strength=strength,
            strength_score=strength_score,
            ema20=ema20,
            ema50=ema50,
            atr=atr,
            regime_trend=regime_trend,
            order_flow=order_flow,
            label_ready_at=timestamp + timedelta(minutes=60),
            status="PENDING"
        )
        db.add(feat_record)
        db.commit()
        logger.info(f"Successfully saved ML features snapshot for {symbol} expiry {expiry_date} (Record ID: {feat_record.id}).")
        return True
    except Exception as e:
        logger.exception(f"Failed to capture ML features: {str(e)}")
        return False

def get_spot_at_target_time(db: Session, symbol: str, target_time: datetime) -> float:
    """
    Finds the spot price from OptionChainSnapshot nearest to the target_time (+/- 3 minutes window).
    """
    snaps = db.query(OptionChainSnapshot).filter(
        OptionChainSnapshot.symbol == symbol,
        OptionChainSnapshot.collection_status == "SUCCESS",
        OptionChainSnapshot.timestamp >= target_time - timedelta(minutes=3),
        OptionChainSnapshot.timestamp <= target_time + timedelta(minutes=3)
    ).all()
    
    if not snaps:
        return None
        
    # Find the snapshot with the smallest absolute time difference
    snaps.sort(key=lambda s: abs((s.timestamp - target_time).total_seconds()))
    return snaps[0].spot_price

def update_ml_labels(db: Session) -> int:
    """
    Retrospectively populates target labels (returns & directions) for feature snapshots
    that are past their label_ready_at mark.
    """
    now = datetime.utcnow()
    pending_records = db.query(MLFeatureSnapshot).filter(
        MLFeatureSnapshot.status == "PENDING",
        MLFeatureSnapshot.label_ready_at <= now
    ).all()
    
    if not pending_records:
        return 0
        
    logger.info(f"Evaluating target labels for {len(pending_records)} pending ML feature snapshots...")
    updated_count = 0
    
    for rec in pending_records:
        try:
            spot_0 = db.query(OptionChainSnapshot).filter(
                OptionChainSnapshot.id == rec.source_snapshot_id
            ).first()
            
            # Fallback if source snapshot is deleted
            price_0 = spot_0.spot_price if spot_0 else None
            if not price_0:
                # Fallback: get nearest spot to the timestamp
                price_0 = get_spot_at_target_time(db, rec.symbol, rec.timestamp)
                
            if not price_0:
                logger.warning(f"Could not resolve initial spot price for feature snapshot ID {rec.id}.")
                rec.status = "COMPLETED" # mark as completed but invalid
                rec.label_quality = "INCOMPLETE"
                rec.available_horizons = json.dumps([])
                db.commit()
                continue
                
            # Fetch spot prices at +15m, +30m, and +60m
            spot_15 = get_spot_at_target_time(db, rec.symbol, rec.timestamp + timedelta(minutes=15))
            spot_30 = get_spot_at_target_time(db, rec.symbol, rec.timestamp + timedelta(minutes=30))
            spot_60 = get_spot_at_target_time(db, rec.symbol, rec.timestamp + timedelta(minutes=60))
            
            horizons = []
            
            # Compute 15m return
            if spot_15 is not None:
                rec.return_15m_points = float(spot_15 - price_0)
                rec.return_15m_pct = float((rec.return_15m_points / price_0) * 100.0)
                
                # Classification target
                if rec.return_15m_pct >= settings.OUTCOME_SUCCESS_THRESHOLD_PCT:
                    rec.direction_15m = "UP"
                elif rec.return_15m_pct <= -settings.OUTCOME_SUCCESS_THRESHOLD_PCT:
                    rec.direction_15m = "DOWN"
                else:
                    rec.direction_15m = "SIDEWAYS"
                horizons.append("15m")
                
            # Compute 30m return
            if spot_30 is not None:
                rec.return_30m_points = float(spot_30 - price_0)
                rec.return_30m_pct = float((rec.return_30m_points / price_0) * 100.0)
                
                if rec.return_30m_pct >= settings.OUTCOME_SUCCESS_THRESHOLD_PCT:
                    rec.direction_30m = "UP"
                elif rec.return_30m_pct <= -settings.OUTCOME_SUCCESS_THRESHOLD_PCT:
                    rec.direction_30m = "DOWN"
                else:
                    rec.direction_30m = "SIDEWAYS"
                horizons.append("30m")
                
            # Compute 60m return
            if spot_60 is not None:
                rec.return_60m_points = float(spot_60 - price_0)
                rec.return_60m_pct = float((rec.return_60m_points / price_0) * 100.0)
                
                if rec.return_60m_pct >= settings.OUTCOME_SUCCESS_THRESHOLD_PCT:
                    rec.direction_60m = "UP"
                elif rec.return_60m_pct <= -settings.OUTCOME_SUCCESS_THRESHOLD_PCT:
                    rec.direction_60m = "DOWN"
                else:
                    rec.direction_60m = "SIDEWAYS"
                horizons.append("60m")
                
            # Label quality classification
            if len(horizons) == 3:
                rec.label_quality = "FULL"
            elif len(horizons) > 0:
                rec.label_quality = "PARTIAL"
            else:
                rec.label_quality = "INCOMPLETE"
                
            rec.available_horizons = json.dumps(horizons)
            rec.status = "COMPLETED"
            db.commit()
            updated_count += 1
        except Exception as err:
            logger.error(f"Failed to compile labels for feature snapshot ID {rec.id}: {str(err)}")
            
    return updated_count
