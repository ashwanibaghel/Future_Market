import logging
import time
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db.models import OptionChainSnapshot, AnalyticsSnapshot, InsightOutcome, SystemMetadata

logger = logging.getLogger(__name__)

def get_metadata(db: Session, key: str, default=None) -> str:
    """
    Retrieves value from system_metadata table.
    """
    row = db.query(SystemMetadata).filter(SystemMetadata.key == key).first()
    if row:
        return row.value
    return default

def set_metadata(db: Session, key: str, value: str):
    """
    Sets or updates a key-value pair in system_metadata table.
    """
    row = db.query(SystemMetadata).filter(SystemMetadata.key == key).first()
    if row:
        row.value = value
    else:
        row = SystemMetadata(key=key, value=value)
        db.add(row)
    db.commit()

def get_prediction_direction(market_state: str) -> str:
    """
    Maps a market buildup state to a directional bias.
    """
    if market_state in ["LONG BUILD-UP", "SHORT COVERING"]:
        return "BULLISH"
    elif market_state in ["SHORT BUILD-UP", "LONG UNWINDING"]:
        return "BEARISH"
    return "NEUTRAL"

def create_pending_outcome(db: Session, snapshot: OptionChainSnapshot, market_state: str) -> bool:
    """
    Creates a pending outcome record for a snapshot if it has a non-neutral buildup state.
    """
    direction = get_prediction_direction(market_state)
    if direction == "NEUTRAL":
        return False

    # Check if already exists
    exists = db.query(InsightOutcome).filter(InsightOutcome.snapshot_id == snapshot.id).first()
    if exists:
        return False

    outcome = InsightOutcome(
        snapshot_id=snapshot.id,
        generated_at=snapshot.timestamp,
        symbol=snapshot.symbol,
        market_state=market_state,
        prediction_direction=direction,
        spot_at_generation=snapshot.spot_price,
        status="PENDING"
    )
    db.add(outcome)
    db.commit()
    logger.info(f"Registered pending outcome for {snapshot.symbol} {market_state} at {snapshot.timestamp} (Snapshot ID: {snapshot.id})")
    return True

def evaluate_outcomes(db: Session):
    """
    Scans pending and partial outcomes and updates them if snapshots at 15m, 30m, or 60m are available.
    """
    logger.info("Evaluating pending/partial insight outcomes...")
    pending_outcomes = db.query(InsightOutcome).filter(InsightOutcome.status != "COMPLETED").all()
    
    if not pending_outcomes:
        logger.info("No pending outcomes to evaluate.")
        return

    now = datetime.utcnow()
    updated_count = 0

    for outcome in pending_outcomes:
        age_seconds = (now - outcome.generated_at).total_seconds()
        
        # Check 5m outcome
        if outcome.spot_after_5m is None:
            # Query snapshot around generated_at + 5 mins (window: +4 to +6 mins)
            t_min = outcome.generated_at + timedelta(minutes=4)
            t_max = outcome.generated_at + timedelta(minutes=6)
            snap = db.query(OptionChainSnapshot).filter(
                OptionChainSnapshot.symbol == outcome.symbol,
                OptionChainSnapshot.collection_status == "SUCCESS",
                OptionChainSnapshot.timestamp >= t_min,
                OptionChainSnapshot.timestamp <= t_max
            ).order_by(OptionChainSnapshot.timestamp.asc()).first()
            if snap:
                outcome.spot_after_5m = snap.spot_price
                outcome.movement_5m_points = snap.spot_price - outcome.spot_at_generation
                outcome.movement_5m_pct = (outcome.movement_5m_points / outcome.spot_at_generation) * 100
                outcome.status = "PARTIAL"

        # Check 15m outcome
        if outcome.spot_after_15m is None:
            # Query snapshot around generated_at + 15 mins (window: +13 to +17 mins)
            t_min = outcome.generated_at + timedelta(minutes=13)
            t_max = outcome.generated_at + timedelta(minutes=17)
            snap = db.query(OptionChainSnapshot).filter(
                OptionChainSnapshot.symbol == outcome.symbol,
                OptionChainSnapshot.collection_status == "SUCCESS",
                OptionChainSnapshot.timestamp >= t_min,
                OptionChainSnapshot.timestamp <= t_max
            ).order_by(OptionChainSnapshot.timestamp.asc()).first()
            if snap:
                outcome.spot_after_15m = snap.spot_price
                outcome.movement_15m_points = snap.spot_price - outcome.spot_at_generation
                outcome.movement_15m_pct = (outcome.movement_15m_points / outcome.spot_at_generation) * 100
                outcome.status = "PARTIAL"

        # Check 30m outcome
        if outcome.spot_after_30m is None:
            # Query snapshot around generated_at + 30 mins (window: +28 to +32 mins)
            t_min = outcome.generated_at + timedelta(minutes=28)
            t_max = outcome.generated_at + timedelta(minutes=32)
            snap = db.query(OptionChainSnapshot).filter(
                OptionChainSnapshot.symbol == outcome.symbol,
                OptionChainSnapshot.collection_status == "SUCCESS",
                OptionChainSnapshot.timestamp >= t_min,
                OptionChainSnapshot.timestamp <= t_max
            ).order_by(OptionChainSnapshot.timestamp.asc()).first()
            if snap:
                outcome.spot_after_30m = snap.spot_price
                outcome.movement_30m_points = snap.spot_price - outcome.spot_at_generation
                outcome.movement_30m_pct = (outcome.movement_30m_points / outcome.spot_at_generation) * 100
                outcome.status = "PARTIAL"

        # Check 60m outcome
        if outcome.spot_after_60m is None:
            # Query snapshot around generated_at + 60 mins (window: +58 to +62 mins)
            t_min = outcome.generated_at + timedelta(minutes=58)
            t_max = outcome.generated_at + timedelta(minutes=62)
            snap = db.query(OptionChainSnapshot).filter(
                OptionChainSnapshot.symbol == outcome.symbol,
                OptionChainSnapshot.collection_status == "SUCCESS",
                OptionChainSnapshot.timestamp >= t_min,
                OptionChainSnapshot.timestamp <= t_max
            ).order_by(OptionChainSnapshot.timestamp.asc()).first()
            if snap:
                outcome.spot_after_60m = snap.spot_price
                outcome.movement_60m_points = snap.spot_price - outcome.spot_at_generation
                outcome.movement_60m_pct = (outcome.movement_60m_points / outcome.spot_at_generation) * 100
                outcome.status = "COMPLETED"

        # Check if outcome is now completed (either just finished 60m or aged out)
        is_completing = (outcome.spot_after_60m is not None) or (age_seconds > 3900 and outcome.status != "COMPLETED")

        if is_completing:
            if age_seconds > 3900:
                outcome.status = "COMPLETED"

            # Perform MFE/MAE Excursion analysis
            t_start = outcome.generated_at
            t_end = outcome.generated_at + timedelta(minutes=60)

            # Query all successful snapshots in the 60m window
            window_snaps = db.query(OptionChainSnapshot).filter(
                OptionChainSnapshot.symbol == outcome.symbol,
                OptionChainSnapshot.collection_status == "SUCCESS",
                OptionChainSnapshot.timestamp >= t_start,
                OptionChainSnapshot.timestamp <= t_end
            ).order_by(OptionChainSnapshot.timestamp.asc()).all()

            # Filter to SAME CALENDAR DAY to handle market close & overnight gap boundaries safely
            window_snaps = [s for s in window_snaps if s.timestamp.date() == t_start.date()]

            if window_snaps:
                best_fav = 0.0
                worst_adv = 0.0
                time_mfe = 0
                time_mae = 0
                spot_gen = outcome.spot_at_generation

                for s in window_snaps:
                    diff = s.spot_price - spot_gen
                    # Excursion direction signs
                    if outcome.prediction_direction == "BULLISH":
                        fav = diff
                        adv = diff
                    else: # BEARISH
                        fav = -diff
                        adv = -diff

                    elapsed_mins = int(round((s.timestamp - t_start).total_seconds() / 60.0))

                    if fav > best_fav:
                        best_fav = fav
                        time_mfe = elapsed_mins

                    if adv < worst_adv:
                        worst_adv = adv
                        time_mae = elapsed_mins

                outcome.max_favorable_move_60m = best_fav
                outcome.max_adverse_move_60m = worst_adv
                outcome.time_to_mfe_minutes = time_mfe
                outcome.time_to_mae_minutes = time_mae

        updated_count += 1

    db.commit()
    logger.info(f"Evaluated {updated_count} outcomes.")

def backfill_insight_outcomes(db: Session):
    """
    Performs a startup scan to create outcomes for all existing historical snapshots
    and evaluates them. Uses watermark checkpointing to scan only new snapshots.
    """
    logger.info("Starting retrospective backfill of insight outcomes...")
    start_time = time.time()

    # Retrieve last successful backfill snapshot ID watermark
    last_id_str = get_metadata(db, "last_successful_backfill_snapshot_id", "0")
    try:
        last_id = int(last_id_str)
    except ValueError:
        last_id = 0

    created_count = 0
    batch_size = 1000

    while True:
        # Fetch snapshots batch
        snapshots = db.query(OptionChainSnapshot).filter(
            OptionChainSnapshot.collection_status == "SUCCESS",
            OptionChainSnapshot.id > last_id
        ).order_by(OptionChainSnapshot.id.asc()).limit(batch_size).all()

        if not snapshots:
            break

        logger.info(f"Processing backfill batch of {len(snapshots)} snapshots above ID {last_id}...")

        for snapshot in snapshots:
            analytics = db.query(AnalyticsSnapshot).filter(
                AnalyticsSnapshot.source_snapshot_id == snapshot.id
            ).first()

            if analytics and analytics.market_state:
                direction = get_prediction_direction(analytics.market_state)
                if direction != "NEUTRAL":
                    # Check if already exists
                    exists = db.query(InsightOutcome).filter(InsightOutcome.snapshot_id == snapshot.id).first()
                    if not exists:
                        outcome = InsightOutcome(
                            snapshot_id=snapshot.id,
                            generated_at=snapshot.timestamp,
                            symbol=snapshot.symbol,
                            market_state=analytics.market_state,
                            prediction_direction=direction,
                            spot_at_generation=snapshot.spot_price,
                            status="PENDING"
                        )
                        db.add(outcome)
                        created_count += 1
            
            # Keep track of the highest snapshot ID processed
            last_id = snapshot.id

        # 1. Commit the outcomes first
        db.commit()

        # 2. Update watermark checkpoint ONLY after successful commit
        set_metadata(db, "last_successful_backfill_snapshot_id", str(last_id))

    # Evaluate pending outcomes
    evaluate_outcomes(db)

    # Save execution duration
    duration_ms = int((time.time() - start_time) * 1000)
    set_metadata(db, "last_backfill_duration_ms", str(duration_ms))

    logger.info(f"Retrospective backfill complete. Created {created_count} outcomes. Duration: {duration_ms} ms. Watermark is now {last_id}.")
