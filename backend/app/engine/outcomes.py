import logging
import time
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db.models import OptionChainSnapshot, AnalyticsSnapshot, InsightOutcome, SystemMetadata, ManualTraderDecision, ObservationLog, TradingSignal

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


def get_success_threshold_points(symbol: str, spot_price: float) -> float:
    """
    Returns point-based movement success threshold dynamically tailored by symbol.
    """
    if symbol == "NIFTY":
        return 15.0
    elif symbol == "BANKNIFTY":
        return 30.0
    elif symbol == "SENSEX":
        return 45.0
    else:
        # For stocks: 0.05% of the spot price as proxy, min 0.1 points
        return max(0.1, round(spot_price * 0.0005, 2))


def cleanup_completed_pending_outcomes(db: Session):
    """
    Finds completed signals and manual decisions that still have PENDING outcomes
    and resolves them to FLAT (meaning the snapshots were missing).
    """
    logger.info("Running self-healing routine for completed records with pending outcomes...")
    
    # 1. Fix TradingSignals
    pending_signals = db.query(TradingSignal).filter(
        TradingSignal.status == "COMPLETED",
        (TradingSignal.outcome_15m == "PENDING") | 
        (TradingSignal.outcome_30m == "PENDING") | 
        (TradingSignal.outcome_60m == "PENDING")
    ).all()
    
    for signal in pending_signals:
        if signal.outcome_15m == "PENDING":
            signal.outcome_15m = "FLAT"
        if signal.outcome_30m == "PENDING":
            signal.outcome_30m = "FLAT"
        if signal.outcome_60m == "PENDING":
            signal.outcome_60m = "FLAT"
            
    # 2. Fix ManualTraderDecisions
    pending_decisions = db.query(ManualTraderDecision).filter(
        ManualTraderDecision.status == "COMPLETED",
        (ManualTraderDecision.outcome_15m == "PENDING") | 
        (ManualTraderDecision.outcome_30m == "PENDING") | 
        (ManualTraderDecision.outcome_60m == "PENDING")
    ).all()
    
    for decision in pending_decisions:
        if decision.outcome_15m == "PENDING":
            decision.outcome_15m = "FLAT"
        if decision.outcome_30m == "PENDING":
            decision.outcome_30m = "FLAT"
        if decision.outcome_60m == "PENDING":
            decision.outcome_60m = "FLAT"
            
    total_fixed = len(pending_signals) + len(pending_decisions)
    if total_fixed > 0:
        db.commit()
        logger.info(f"Self-healed {len(pending_signals)} signals and {len(pending_decisions)} manual decisions.")


def evaluate_trading_signals(db: Session):
    """
    Scans pending trading signals and updates their outcomes (15m, 30m, 60m)
    using future snapshots.
    """
    # Run self-healing first to clean up any past corrupted states
    cleanup_completed_pending_outcomes(db)
    
    logger.info("Evaluating pending trading signals...")
    from app.db.models import TradingSignal, OptionChainSnapshot

    
    pending_signals = db.query(TradingSignal).filter(TradingSignal.status != "COMPLETED").all()
    if not pending_signals:
        logger.info("No pending trading signals to evaluate.")
        return

    now = datetime.utcnow()
    updated_count = 0

    for signal in pending_signals:
        age_seconds = (now - signal.timestamp).total_seconds()
        threshold = get_success_threshold_points(signal.symbol, signal.spot_price)
        
        # Check 15m outcome
        if signal.spot_after_15m is None:
            t_min = signal.timestamp + timedelta(minutes=13)
            t_max = signal.timestamp + timedelta(minutes=17)
            snap = db.query(OptionChainSnapshot).filter(
                OptionChainSnapshot.symbol == signal.symbol,
                OptionChainSnapshot.collection_status == "SUCCESS",
                OptionChainSnapshot.timestamp >= t_min,
                OptionChainSnapshot.timestamp <= t_max
            ).order_by(OptionChainSnapshot.timestamp.asc()).first()
            if snap:
                signal.spot_after_15m = snap.spot_price
                signal.move_15m_points = snap.spot_price - signal.spot_price
                signal.move_15m_pct = (signal.move_15m_points / signal.spot_price) * 100
                
                # Determine outcome_15m
                if signal.signal_type == "BUY_CALL":
                    if signal.move_15m_points >= threshold:
                        signal.outcome_15m = "WIN"
                    elif signal.move_15m_points <= -threshold:
                        signal.outcome_15m = "LOSS"
                    else:
                        signal.outcome_15m = "FLAT"
                elif signal.signal_type == "BUY_PUT":
                    if signal.move_15m_points <= -threshold:
                        signal.outcome_15m = "WIN"
                    elif signal.move_15m_points >= threshold:
                        signal.outcome_15m = "LOSS"
                    else:
                        signal.outcome_15m = "FLAT"
                else: # NO_TRADE
                    signal.outcome_15m = "FLAT"

        # Check 30m outcome
        if signal.spot_after_30m is None:
            t_min = signal.timestamp + timedelta(minutes=28)
            t_max = signal.timestamp + timedelta(minutes=32)
            snap = db.query(OptionChainSnapshot).filter(
                OptionChainSnapshot.symbol == signal.symbol,
                OptionChainSnapshot.collection_status == "SUCCESS",
                OptionChainSnapshot.timestamp >= t_min,
                OptionChainSnapshot.timestamp <= t_max
            ).order_by(OptionChainSnapshot.timestamp.asc()).first()
            if snap:
                signal.spot_after_30m = snap.spot_price
                signal.move_30m_points = snap.spot_price - signal.spot_price
                signal.move_30m_pct = (signal.move_30m_points / signal.spot_price) * 100
                
                # Determine outcome_30m
                if signal.signal_type == "BUY_CALL":
                    if signal.move_30m_points >= threshold:
                        signal.outcome_30m = "WIN"
                    elif signal.move_30m_points <= -threshold:
                        signal.outcome_30m = "LOSS"
                    else:
                        signal.outcome_30m = "FLAT"
                elif signal.signal_type == "BUY_PUT":
                    if signal.move_30m_points <= -threshold:
                        signal.outcome_30m = "WIN"
                    elif signal.move_30m_points >= threshold:
                        signal.outcome_30m = "LOSS"
                    else:
                        signal.outcome_30m = "FLAT"
                else: # NO_TRADE
                    signal.outcome_30m = "FLAT"

        # Check 60m outcome
        if signal.spot_after_60m is None:
            t_min = signal.timestamp + timedelta(minutes=58)
            t_max = signal.timestamp + timedelta(minutes=62)
            snap = db.query(OptionChainSnapshot).filter(
                OptionChainSnapshot.symbol == signal.symbol,
                OptionChainSnapshot.collection_status == "SUCCESS",
                OptionChainSnapshot.timestamp >= t_min,
                OptionChainSnapshot.timestamp <= t_max
            ).order_by(OptionChainSnapshot.timestamp.asc()).first()
            if snap:
                signal.spot_after_60m = snap.spot_price
                signal.move_60m_points = snap.spot_price - signal.spot_price
                signal.move_60m_pct = (signal.move_60m_points / signal.spot_price) * 100
                
                # Determine outcome_60m
                if signal.signal_type == "BUY_CALL":
                    if signal.move_60m_points >= threshold:
                        signal.outcome_60m = "WIN"
                    elif signal.move_60m_points <= -threshold:
                        signal.outcome_60m = "LOSS"
                    else:
                        signal.outcome_60m = "FLAT"
                elif signal.signal_type == "BUY_PUT":
                    if signal.move_60m_points <= -threshold:
                        signal.outcome_60m = "WIN"
                    elif signal.move_60m_points >= threshold:
                        signal.outcome_60m = "LOSS"
                    else:
                        signal.outcome_60m = "FLAT"
                else: # NO_TRADE
                    signal.outcome_60m = "FLAT"
                
                signal.status = "COMPLETED"

        # Consolidate completion/age-out and resolve any remaining pending outcomes
        if signal.status == "COMPLETED" or age_seconds > 3900:
            if signal.outcome_15m == "PENDING" or signal.spot_after_15m is None:
                signal.outcome_15m = "FLAT"
            if signal.outcome_30m == "PENDING" or signal.spot_after_30m is None:
                signal.outcome_30m = "FLAT"
            if signal.outcome_60m == "PENDING" or signal.spot_after_60m is None:
                signal.outcome_60m = "FLAT"
            signal.status = "COMPLETED"

        updated_count += 1

    db.commit()
    logger.info(f"Evaluated {updated_count} trading signals.")


def backfill_trading_signals(db: Session):
    """
    Startup scan to create and evaluate TradingSignal records for all existing historical snapshots.
    """
    logger.info("Starting retrospective backfill of trading signals...")
    from app.db.models import TradingSignal, OptionChainSnapshot
    from app.engine.signals import generate_trading_signal
    
    # Retrieve last successful backfill snapshot ID watermark for signals
    last_id_str = get_metadata(db, "last_backfilled_signal_snapshot_id", "0")
    try:
        last_id = int(last_id_str)
    except ValueError:
        last_id = 0

    batch_size = 500
    created_count = 0
    
    while True:
        snapshots = db.query(OptionChainSnapshot).filter(
            OptionChainSnapshot.collection_status == "SUCCESS",
            OptionChainSnapshot.id > last_id
        ).order_by(OptionChainSnapshot.id.asc()).limit(batch_size).all()
        
        if not snapshots:
            break
            
        for snap in snapshots:
            sig = generate_trading_signal(db, snap.id)
            if sig:
                created_count += 1
            last_id = snap.id
            
        db.commit()
        set_metadata(db, "last_backfilled_signal_snapshot_id", str(last_id))
        
    logger.info(f"Trading signals backfill complete. Created {created_count} trading signals.")
    
    # Evaluate outcomes of all trading signals
    evaluate_trading_signals(db)


def evaluate_manual_decisions(db: Session):
    """
    Scans pending manual decisions and updates their outcomes (15m, 30m, 60m)
    using future snapshots.
    """
    logger.info("Evaluating pending manual trader decisions...")
    
    pending = db.query(ManualTraderDecision).filter(ManualTraderDecision.status != "COMPLETED").all()
    if not pending:
        logger.info("No pending manual decisions to evaluate.")
        return

    now = datetime.utcnow()
    updated_count = 0

    for decision in pending:
        age_seconds = (now - decision.timestamp).total_seconds()
        threshold = get_success_threshold_points(decision.symbol, decision.spot_price)
        
        # Check 15m outcome
        if decision.spot_after_15m is None:
            t_min = decision.timestamp + timedelta(minutes=13)
            t_max = decision.timestamp + timedelta(minutes=17)
            snap = db.query(OptionChainSnapshot).filter(
                OptionChainSnapshot.symbol == decision.symbol,
                OptionChainSnapshot.collection_status == "SUCCESS",
                OptionChainSnapshot.timestamp >= t_min,
                OptionChainSnapshot.timestamp <= t_max
            ).order_by(OptionChainSnapshot.timestamp.asc()).first()
            if snap:
                decision.spot_after_15m = snap.spot_price
                decision.move_15m_points = snap.spot_price - decision.spot_price
                decision.move_15m_pct = (decision.move_15m_points / decision.spot_price) * 100
                decision.status = "PARTIAL"
                
                # Determine outcome_15m
                if decision.decision_type == "BUY_CALL":
                    if decision.move_15m_points >= threshold:
                        decision.outcome_15m = "WIN"
                    elif decision.move_15m_points <= -threshold:
                        decision.outcome_15m = "LOSS"
                    else:
                        decision.outcome_15m = "FLAT"
                elif decision.decision_type == "BUY_PUT":
                    if decision.move_15m_points <= -threshold:
                        decision.outcome_15m = "WIN"
                    elif decision.move_15m_points >= threshold:
                        decision.outcome_15m = "LOSS"
                    else:
                        decision.outcome_15m = "FLAT"
                else: # STAY_OUT / NO_TRADE
                    decision.outcome_15m = "FLAT"

        # Check 30m outcome
        if decision.spot_after_30m is None:
            t_min = decision.timestamp + timedelta(minutes=28)
            t_max = decision.timestamp + timedelta(minutes=32)
            snap = db.query(OptionChainSnapshot).filter(
                OptionChainSnapshot.symbol == decision.symbol,
                OptionChainSnapshot.collection_status == "SUCCESS",
                OptionChainSnapshot.timestamp >= t_min,
                OptionChainSnapshot.timestamp <= t_max
            ).order_by(OptionChainSnapshot.timestamp.asc()).first()
            if snap:
                decision.spot_after_30m = snap.spot_price
                decision.move_30m_points = snap.spot_price - decision.spot_price
                decision.move_30m_pct = (decision.move_30m_points / decision.spot_price) * 100
                decision.status = "PARTIAL"
                
                # Determine outcome_30m
                if decision.decision_type == "BUY_CALL":
                    if decision.move_30m_points >= threshold:
                        decision.outcome_30m = "WIN"
                    elif decision.move_30m_points <= -threshold:
                        decision.outcome_30m = "LOSS"
                    else:
                        decision.outcome_30m = "FLAT"
                elif decision.decision_type == "BUY_PUT":
                    if decision.move_30m_points <= -threshold:
                        decision.outcome_30m = "WIN"
                    elif decision.move_30m_points >= threshold:
                        decision.outcome_30m = "LOSS"
                    else:
                        decision.outcome_30m = "FLAT"
                else: # STAY_OUT / NO_TRADE
                    decision.outcome_30m = "FLAT"

        # Check 60m outcome
        if decision.spot_after_60m is None:
            t_min = decision.timestamp + timedelta(minutes=58)
            t_max = decision.timestamp + timedelta(minutes=62)
            snap = db.query(OptionChainSnapshot).filter(
                OptionChainSnapshot.symbol == decision.symbol,
                OptionChainSnapshot.collection_status == "SUCCESS",
                OptionChainSnapshot.timestamp >= t_min,
                OptionChainSnapshot.timestamp <= t_max
            ).order_by(OptionChainSnapshot.timestamp.asc()).first()
            if snap:
                decision.spot_after_60m = snap.spot_price
                decision.move_60m_points = snap.spot_price - decision.spot_price
                decision.move_60m_pct = (decision.move_60m_points / decision.spot_price) * 100
                
                # Determine outcome_60m
                if decision.decision_type == "BUY_CALL":
                    if decision.move_60m_points >= threshold:
                        decision.outcome_60m = "WIN"
                    elif decision.move_60m_points <= -threshold:
                        decision.outcome_60m = "LOSS"
                    else:
                        decision.outcome_60m = "FLAT"
                elif decision.decision_type == "BUY_PUT":
                    if decision.move_60m_points <= -threshold:
                        decision.outcome_60m = "WIN"
                    elif decision.move_60m_points >= threshold:
                        decision.outcome_60m = "LOSS"
                    else:
                        decision.outcome_60m = "FLAT"
                else: # STAY_OUT / NO_TRADE
                    decision.outcome_60m = "FLAT"
                
                decision.status = "COMPLETED"

        # Consolidate completion/age-out and resolve any remaining pending outcomes
        if decision.status == "COMPLETED" or age_seconds > 3900:
            if decision.outcome_15m == "PENDING" or decision.spot_after_15m is None:
                decision.outcome_15m = "FLAT"
            if decision.outcome_30m == "PENDING" or decision.spot_after_30m is None:
                decision.outcome_30m = "FLAT"
            if decision.outcome_60m == "PENDING" or decision.spot_after_60m is None:
                decision.outcome_60m = "FLAT"
            decision.status = "COMPLETED"

        updated_count += 1

    db.commit()
    logger.info(f"Evaluated {updated_count} manual decisions.")


def evaluate_observation_logs(db: Session):
    """
    Syncs and resolves outcome results in the ObservationLog table from their linked sources.
    """
    logger.info("Evaluating pending daily observation logs...")
    
    pending = db.query(ObservationLog).filter(ObservationLog.status != "COMPLETED").all()
    if not pending:
        logger.info("No pending observation logs to evaluate.")
        return

    updated_count = 0
    
    for log in pending:
        # 1. If linked to manual decision
        if log.manual_decision_id:
            m_dec = db.query(ManualTraderDecision).filter(ManualTraderDecision.id == log.manual_decision_id).first()
            if m_dec:
                log.result_15m = m_dec.outcome_15m
                log.result_30m = m_dec.outcome_30m
                log.result_60m = m_dec.outcome_60m
                log.status = m_dec.status
                updated_count += 1
                
        # 2. Else if linked to system signal
        elif log.system_signal_id:
            sys_sig = db.query(TradingSignal).filter(TradingSignal.id == log.system_signal_id).first()
            if sys_sig:
                log.result_15m = sys_sig.outcome_15m
                log.result_30m = sys_sig.outcome_30m
                log.result_60m = sys_sig.outcome_60m
                log.status = sys_sig.status
                updated_count += 1
        else:
            # Unlinked log, mark completed
            log.status = "COMPLETED"
            updated_count += 1
            
    db.commit()
    logger.info(f"Synchronized/Evaluated {updated_count} observation logs.")

