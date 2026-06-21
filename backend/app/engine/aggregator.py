import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db.models import (
    OptionChainSnapshot, OptionChainStrike,
    OptionChainSnapshot5m, OptionChainStrike5m, AnalyticsSnapshot5m,
    OptionChainSnapshot15m, OptionChainStrike15m, AnalyticsSnapshot15m
)
from app.engine.analytics import generate_analytics_snapshot_generic

logger = logging.getLogger(__name__)

def round_down_minutes(dt: datetime, minutes: int) -> datetime:
    return dt.replace(minute=(dt.minute // minutes) * minutes, second=0, microsecond=0)

def aggregate_snapshots(db: Session, interval_minutes: int):
    """
    Finds all unaggregated 1-minute snapshots for the interval and rolls them up.
    interval_minutes can be 5 or 15.
    """
    if interval_minutes == 5:
        snapshot_cls = OptionChainSnapshot5m
        strike_cls = OptionChainStrike5m
        analytics_cls = AnalyticsSnapshot5m
        round_fn = lambda dt: round_down_minutes(dt, 5)
    elif interval_minutes == 15:
        snapshot_cls = OptionChainSnapshot15m
        strike_cls = OptionChainStrike15m
        analytics_cls = AnalyticsSnapshot15m
        round_fn = lambda dt: round_down_minutes(dt, 15)
    else:
        raise ValueError("Only 5 or 15 minute aggregates are supported.")

    # Find the last aggregated snapshot to know where to start
    last_agg = db.query(snapshot_cls).order_by(snapshot_cls.timestamp.desc()).first()
    if last_agg:
        start_time = last_agg.timestamp
    else:
        # Get oldest 1-minute snapshot timestamp
        oldest = db.query(OptionChainSnapshot).order_by(OptionChainSnapshot.timestamp.asc()).first()
        if not oldest:
            logger.info("No 1-minute snapshots available to aggregate.")
            return
        start_time = round_fn(oldest.timestamp)

    end_time = round_fn(datetime.utcnow())

    logger.info(f"Running {interval_minutes}m aggregation from {start_time} to {end_time}...")

    t = start_time
    aggregated_count = 0
    while t + timedelta(minutes=interval_minutes) <= end_time:
        interval_start = t
        interval_end = t + timedelta(minutes=interval_minutes)
        
        # Check if this aggregate snapshot already exists in DB
        exists = db.query(snapshot_cls).filter(snapshot_cls.timestamp == interval_end).first()
        if exists:
            t = interval_end
            continue

        # Get all 1-minute successful snapshots in this interval
        snapshots_in_interval = db.query(OptionChainSnapshot).filter(
            OptionChainSnapshot.timestamp >= interval_start,
            OptionChainSnapshot.timestamp < interval_end,
            OptionChainSnapshot.collection_status == "SUCCESS"
        ).order_by(OptionChainSnapshot.timestamp.asc()).all()

        if not snapshots_in_interval:
            t = interval_end
            continue

        # Group by symbol & expiry
        groups = {}
        for s in snapshots_in_interval:
            key = (s.symbol, s.expiry_date)
            if key not in groups:
                groups[key] = []
            groups[key].append(s)

        for (symbol, expiry_date), group_snapshots in groups.items():
            last_snap = group_snapshots[-1]
            
            # Fetch all strikes for these snapshots
            snap_ids = [s.id for s in group_snapshots]
            all_strikes = db.query(OptionChainStrike).filter(
                OptionChainStrike.snapshot_id.in_(snap_ids)
            ).all()

            if not all_strikes:
                continue

            # Group strikes by strike price
            strike_map = {}
            for st in all_strikes:
                if st.strike not in strike_map:
                    strike_map[st.strike] = []
                strike_map[st.strike].append(st)

            # Create the aggregated snapshot record
            agg_snapshot = snapshot_cls(
                timestamp=interval_end, # end of interval represents state at that point
                symbol=symbol,
                instrument_type=last_snap.instrument_type,
                expiry_date=expiry_date,
                spot_price=last_snap.spot_price, # Close/Last spot price
                provider=last_snap.provider,
                collection_status="SUCCESS",
                collection_duration_ms=int(sum(s.collection_duration_ms for s in group_snapshots) / len(group_snapshots))
            )
            db.add(agg_snapshot)
            db.flush()

            # Build aggregated strikes
            agg_strikes = []
            
            # To map strike snap times chronologically, let's create a map of snapshot_id to timestamp
            snap_time_map = {s.id: s.timestamp for s in group_snapshots}

            for strike_price, strike_records in strike_map.items():
                # Sort records chronologically
                strike_records = sorted(strike_records, key=lambda r: snap_time_map[r.snapshot_id])
                
                # NSE Change OI and Volume are cumulative session values.
                # Adding them would cause double-counting.
                # Aggregation Rules:
                # - OI -> Last Value
                # - Change OI -> Last Value (represents cumulative change up to interval end)
                # - Volume -> Last Value (represents cumulative volume up to interval end)
                # - LTP -> Last Value
                # - Bid/Ask -> Last Value
                # - IV -> Average (smooths out data glitches/noise)
                
                last_rec = strike_records[-1]
                avg_call_iv = sum(r.call_iv for r in strike_records) / len(strike_records)
                avg_put_iv = sum(r.put_iv for r in strike_records) / len(strike_records)

                agg_strike = strike_cls(
                    snapshot_id=agg_snapshot.id,
                    strike=strike_price,
                    call_oi=last_rec.call_oi,
                    call_change_oi=last_rec.call_change_oi,
                    call_volume=last_rec.call_volume,
                    call_iv=avg_call_iv,
                    call_ltp=last_rec.call_ltp,
                    call_bid=last_rec.call_bid,
                    call_ask=last_rec.call_ask,
                    put_oi=last_rec.put_oi,
                    put_change_oi=last_rec.put_change_oi,
                    put_volume=last_rec.put_volume,
                    put_iv=avg_put_iv,
                    put_ltp=last_rec.put_ltp,
                    put_bid=last_rec.put_bid,
                    put_ask=last_rec.put_ask
                )
                agg_strikes.append(agg_strike)

            db.bulk_save_objects(agg_strikes)
            db.commit()

            # Run analytics generation for this aggregated snapshot (without generated_insights)
            try:
                generate_analytics_snapshot_generic(
                    db,
                    agg_snapshot.id,
                    snapshot_cls=snapshot_cls,
                    strike_cls=strike_cls,
                    analytics_cls=analytics_cls,
                    run_insights=False
                )
                # Capture ML Features for the aggregated snapshot
                from app.engine.ml_store import capture_ml_features
                capture_ml_features(db, agg_snapshot.id, timeframe=f"{interval_minutes}m")
            except Exception as ae:
                logger.error(f"Failed to generate analytics or capture ML features for aggregated snapshot {agg_snapshot.id}: {str(ae)}")

            aggregated_count += 1

        t = interval_end

    logger.info(f"Aggregation complete. Created {aggregated_count} aggregated {interval_minutes}m snapshots.")


def run_retention_pruner(db: Session):
    """
    Cleans up old records according to retention settings.
    Includes safety logic to never delete the most recent successful snapshot for each symbol.
    """
    from app.config import settings
    logger.info("Running database retention pruner...")

    now = datetime.utcnow()
    
    # 1. Identify latest successful snapshot IDs to protect from deletion (dashboard safety)
    protected_snapshot_ids = set()
    protected_snapshot_5m_ids = set()
    protected_snapshot_15m_ids = set()

    for symbol in settings.SYMBOLS:
        # Protect latest 1m snapshot
        latest_1m = db.query(OptionChainSnapshot).filter(
            OptionChainSnapshot.symbol == symbol,
            OptionChainSnapshot.collection_status == "SUCCESS"
        ).order_by(OptionChainSnapshot.timestamp.desc()).first()
        if latest_1m:
            protected_snapshot_ids.add(latest_1m.id)
            
        # Protect latest 5m snapshot
        latest_5m = db.query(OptionChainSnapshot5m).filter(
            OptionChainSnapshot5m.symbol == symbol,
            OptionChainSnapshot5m.collection_status == "SUCCESS"
        ).order_by(OptionChainSnapshot5m.timestamp.desc()).first()
        if latest_5m:
            protected_snapshot_5m_ids.add(latest_5m.id)
            
        # Protect latest 15m snapshot
        latest_15m = db.query(OptionChainSnapshot15m).filter(
            OptionChainSnapshot15m.symbol == symbol,
            OptionChainSnapshot15m.collection_status == "SUCCESS"
        ).order_by(OptionChainSnapshot15m.timestamp.desc()).first()
        if latest_15m:
            protected_snapshot_15m_ids.add(latest_15m.id)

    # 2. Prune Raw response table (Older than settings.RAW_RESPONSE_RETENTION_DAYS)
    raw_cutoff = now - timedelta(days=settings.RAW_RESPONSE_RETENTION_DAYS)
    from app.db.models import RawProviderResponse, AnalyticsSnapshot, GeneratedInsight
    deleted_raw = db.query(RawProviderResponse).filter(RawProviderResponse.timestamp < raw_cutoff).delete()
    
    # 3. Prune 1-minute snapshots & strikes & analytics (Older than settings.ONE_MIN_RETENTION_DAYS)
    one_min_cutoff = now - timedelta(days=settings.ONE_MIN_RETENTION_DAYS)
    
    snaps_to_delete_query = db.query(OptionChainSnapshot).filter(
        OptionChainSnapshot.timestamp < one_min_cutoff
    )
    if protected_snapshot_ids:
        snaps_to_delete_query = snaps_to_delete_query.filter(
            OptionChainSnapshot.id.not_in(list(protected_snapshot_ids))
        )
    snaps_to_delete = snaps_to_delete_query.all()
    snap_ids_to_delete = [s.id for s in snaps_to_delete]

    if snap_ids_to_delete:
        # Delete related analytics snapshots
        db.query(AnalyticsSnapshot).filter(AnalyticsSnapshot.source_snapshot_id.in_(snap_ids_to_delete)).delete(synchronize_session=False)
        # Explicitly delete child strikes (since SQLite query delete doesn't cascade automatically)
        db.query(OptionChainStrike).filter(OptionChainStrike.snapshot_id.in_(snap_ids_to_delete)).delete(synchronize_session=False)
        # Delete actual snapshots
        db.query(OptionChainSnapshot).filter(OptionChainSnapshot.id.in_(snap_ids_to_delete)).delete(synchronize_session=False)

    # 4. Prune 5-minute snapshots & strikes & analytics (Older than settings.FIVE_MIN_RETENTION_DAYS)
    five_min_cutoff = now - timedelta(days=settings.FIVE_MIN_RETENTION_DAYS)
    snaps5m_to_delete_query = db.query(OptionChainSnapshot5m).filter(
        OptionChainSnapshot5m.timestamp < five_min_cutoff
    )
    if protected_snapshot_5m_ids:
        snaps5m_to_delete_query = snaps5m_to_delete_query.filter(
            OptionChainSnapshot5m.id.not_in(list(protected_snapshot_5m_ids))
        )
    snaps5m_to_delete = snaps5m_to_delete_query.all()
    snap5m_ids_to_delete = [s.id for s in snaps5m_to_delete]

    if snap5m_ids_to_delete:
        db.query(AnalyticsSnapshot5m).filter(AnalyticsSnapshot5m.source_snapshot_id.in_(snap5m_ids_to_delete)).delete(synchronize_session=False)
        db.query(OptionChainStrike5m).filter(OptionChainStrike5m.snapshot_id.in_(snap5m_ids_to_delete)).delete(synchronize_session=False)
        db.query(OptionChainSnapshot5m).filter(OptionChainSnapshot5m.id.in_(snap5m_ids_to_delete)).delete(synchronize_session=False)

    # 5. Prune 15-minute snapshots & strikes & analytics (Older than settings.FIFTEEN_MIN_RETENTION_DAYS)
    fifteen_min_cutoff = now - timedelta(days=settings.FIFTEEN_MIN_RETENTION_DAYS)
    snaps15m_to_delete_query = db.query(OptionChainSnapshot15m).filter(
        OptionChainSnapshot15m.timestamp < fifteen_min_cutoff
    )
    if protected_snapshot_15m_ids:
        snaps15m_to_delete_query = snaps15m_to_delete_query.filter(
            OptionChainSnapshot15m.id.not_in(list(protected_snapshot_15m_ids))
        )
    snaps15m_to_delete = snaps15m_to_delete_query.all()
    snap15m_ids_to_delete = [s.id for s in snaps15m_to_delete]

    if snap15m_ids_to_delete:
        db.query(AnalyticsSnapshot15m).filter(AnalyticsSnapshot15m.source_snapshot_id.in_(snap15m_ids_to_delete)).delete(synchronize_session=False)
        db.query(OptionChainStrike15m).filter(OptionChainStrike15m.snapshot_id.in_(snap15m_ids_to_delete)).delete(synchronize_session=False)
        db.query(OptionChainSnapshot15m).filter(OptionChainSnapshot15m.id.in_(snap15m_ids_to_delete)).delete(synchronize_session=False)

    # 6. Prune generated insights (older than 90 days)
    insights_cutoff = now - timedelta(days=90)
    deleted_insights = db.query(GeneratedInsight).filter(GeneratedInsight.timestamp < insights_cutoff).delete()

    db.commit()
    logger.info(
        f"Retention pruning complete. Deleted: "
        f"{deleted_raw} raw response records, "
        f"{len(snap_ids_to_delete)} 1-minute snapshots, "
        f"{len(snap5m_ids_to_delete)} 5-minute snapshots, "
        f"{len(snap15m_ids_to_delete)} 15-minute snapshots, "
        f"{deleted_insights} insight records."
    )
