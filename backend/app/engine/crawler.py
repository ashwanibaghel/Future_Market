import asyncio
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.config import settings
from app.providers import get_provider
from app.db.models import OptionChainSnapshot, OptionChainStrike, RawProviderResponse
from app.engine.analytics import generate_analytics_snapshot
from app.engine.ml_store import capture_ml_features

from datetime import timezone, timedelta

logger = logging.getLogger(__name__)

def is_market_open() -> bool:
    """
    Checks if the current time is during standard Indian market hours.
    IST (UTC +5:30) Monday to Friday, 09:15 AM to 03:30 PM.
    """
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist_tz)
    
    # Check weekday (0 = Monday, ..., 6 = Sunday)
    if now_ist.weekday() >= 5:
        return False
        
    # Check time (09:15 to 15:30)
    market_start = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
    market_end = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)
    
    return market_start <= now_ist <= market_end

async def fetch_and_save(symbol: str, db: Session) -> bool:
    """
    Fetches option chain for a symbol, saves raw response, parses and bulk-saves snapshots + strikes
    for all tracked expiry dates, and runs the analytics engine to populate analytics_snapshots.
    """
    logger.info(f"Running background fetch and save for {symbol}...")
    try:
        provider = get_provider(settings.ACTIVE_PROVIDER)
        results = await provider.fetch_option_chain(symbol)
        
        if not results:
            logger.warning(f"No option chain results parsed for {symbol}.")
            return False
            
        # 1. Save Raw Response exactly once
        raw_response = RawProviderResponse(
            timestamp=datetime.utcnow(),
            provider=settings.ACTIVE_PROVIDER,
            symbol=symbol,
            payload_json=results[0]['raw_payload']
        )
        db.add(raw_response)
        db.commit()
        
        # 2. Process each expiry date snapshot
        for result in results:
            start_time = datetime.utcnow()
            snapshot = OptionChainSnapshot(
                timestamp=datetime.utcnow(),
                symbol=result['symbol'],
                instrument_type="INDEX",
                expiry_date=result['expiry_date'],
                spot_price=result['spot_price'],
                provider=settings.ACTIVE_PROVIDER,
                collection_status="SUCCESS",
                collection_duration_ms=0
            )
            db.add(snapshot)
            db.commit()
            db.refresh(snapshot)
            
            # Update duration
            duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            snapshot.collection_duration_ms = duration
            db.commit()
            
            # 3. Save Strikes in Bulk
            strikes_to_save = []
            for item in result['strikes']:
                strike_record = OptionChainStrike(
                    snapshot_id=snapshot.id,
                    strike=item['strike'],
                    call_oi=item['call_oi'],
                    call_change_oi=item['call_change_oi'],
                    call_volume=item['call_volume'],
                    call_iv=item['call_iv'],
                    call_ltp=item['call_ltp'],
                    call_bid=item['call_bid'],
                    call_ask=item['call_ask'],
                    call_delta=item.get('call_delta', 0.0),
                    call_gamma=item.get('call_gamma', 0.0),
                    call_theta=item.get('call_theta', 0.0),
                    call_vega=item.get('call_vega', 0.0),
                    put_oi=item['put_oi'],
                    put_change_oi=item['put_change_oi'],
                    put_volume=item['put_volume'],
                    put_iv=item['put_iv'],
                    put_ltp=item['put_ltp'],
                    put_bid=item['put_bid'],
                    put_ask=item['put_ask'],
                    put_delta=item.get('put_delta', 0.0),
                    put_gamma=item.get('put_gamma', 0.0),
                    put_theta=item.get('put_theta', 0.0),
                    put_vega=item.get('put_vega', 0.0)
                )
                strikes_to_save.append(strike_record)
            
            db.bulk_save_objects(strikes_to_save)
            db.commit()
            logger.info(f"Successfully saved {len(strikes_to_save)} strikes for {symbol} expiry {result['expiry_date']} (Snapshot ID: {snapshot.id}).")
            
            # 4. Generate Analytics Snapshot
            try:
                generate_analytics_snapshot(db, snapshot.id)
                logger.info(f"Successfully generated analytics snapshot for {symbol} expiry {result['expiry_date']} (Snapshot ID: {snapshot.id}).")
                # Capture ML features for timeframe 1m
                capture_ml_features(db, snapshot.id, timeframe="1m")
                
                # Generate Trading Signal
                from app.engine.signals import generate_trading_signal
                generate_trading_signal(db, snapshot.id)
            except Exception as ae:
                logger.exception(f"Failed to generate analytics snapshot/signals for {symbol} expiry {result['expiry_date']}: {str(ae)}")
                
        return True
    except Exception as e:
        logger.exception(f"Failed to fetch/save {symbol}: {str(e)}")
        # Log failure record in snapshot to update health endpoint
        try:
            snapshot = OptionChainSnapshot(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                instrument_type="INDEX",
                expiry_date="UNKNOWN",
                spot_price=0.0,
                provider=settings.ACTIVE_PROVIDER,
                collection_status="ERROR",
                collection_duration_ms=0
            )
            db.add(snapshot)
            db.commit()
            logger.info(f"Logged ERROR snapshot status for {symbol} in database.")
        except Exception as db_err:
            logger.exception(f"Failed to log error snapshot in DB: {str(db_err)}")
        return False


def run_sync_aggregations():
    from app.db.session import SessionLocal
    from app.engine.aggregator import aggregate_snapshots
    db = SessionLocal()
    try:
        aggregate_snapshots(db, 5)
        aggregate_snapshots(db, 15)
    finally:
        db.close()

def run_sync_pruner():
    from app.db.session import SessionLocal
    from app.engine.aggregator import run_retention_pruner
    db = SessionLocal()
    try:
        run_retention_pruner(db)
    finally:
        db.close()

def run_sync_outcomes_evaluation():
    """
    Evaluates pending/partial InsightOutcome records using available snapshots.
    Runs in a separate thread to avoid blocking the async event loop.
    """
    from app.db.session import SessionLocal
    from app.engine.outcomes import evaluate_outcomes
    db = SessionLocal()
    try:
        evaluate_outcomes(db)
    finally:
        db.close()

def run_sync_ml_label_update():
    """
    Evaluates pending ML target labels retrospectively.
    Runs in a separate thread to avoid blocking the async event loop.
    """
    from app.db.session import SessionLocal
    from app.engine.ml_store import update_ml_labels
    db = SessionLocal()
    try:
        update_ml_labels(db)
    finally:
        db.close()

def run_sync_signals_evaluation():
    """
    Evaluates pending TradingSignal records using available snapshots.
    Runs in a separate thread to avoid blocking the async event loop.
    """
    from app.db.session import SessionLocal
    from app.engine.outcomes import evaluate_trading_signals
    db = SessionLocal()
    try:
        evaluate_trading_signals(db)
    finally:
        db.close()

def run_sync_manual_decisions_evaluation():
    """
    Evaluates pending ManualTraderDecision records using available snapshots.
    """
    from app.db.session import SessionLocal
    from app.engine.outcomes import evaluate_manual_decisions
    db = SessionLocal()
    try:
        evaluate_manual_decisions(db)
    finally:
        db.close()

def run_sync_observation_logs_evaluation():
    """
    Evaluates pending ObservationLog records using available snapshots.
    """
    from app.db.session import SessionLocal
    from app.engine.outcomes import evaluate_observation_logs
    db = SessionLocal()
    try:
        evaluate_observation_logs(db)
    finally:
        db.close()

def run_startup_backfill():
    """
    On startup, creates InsightOutcome and TradingSignal records for all historical snapshots and evaluates them.
    Runs once in a background thread.
    """
    from app.db.session import SessionLocal
    from app.engine.outcomes import backfill_insight_outcomes, backfill_trading_signals
    db = SessionLocal()
    try:
        backfill_insight_outcomes(db)
        backfill_trading_signals(db)
    except Exception as e:
        logger.exception(f"Startup backfill failed: {str(e)}")
    finally:
        db.close()

async def start_crawler_loop():
    """
    Background loop that runs continuously, polling the provider at settings.POLL_INTERVAL_SECONDS.
    Wrapped in never-crashing try-except-finally blocks.
    """
    logger.info("Starting background crawler loop...")
    from app.db.session import SessionLocal
    
    # Simple delay on startup to let server initialize
    await asyncio.sleep(5.0)
    
    # Run startup backfill of InsightOutcomes for historical snapshots (non-blocking)
    try:
        logger.info("Running startup InsightOutcome backfill in background thread...")
        await asyncio.to_thread(run_startup_backfill)
    except Exception as bf_err:
        logger.exception(f"Startup backfill error: {str(bf_err)}")
    
    last_prune_time = None
    
    while True:
        try:
            logger.info("Starting a new crawler poll cycle...")
            db = SessionLocal()
            try:
                # 1. Fetch and save raw/1m data (only if market is open or using non-live testing provider)
                if is_market_open() or settings.ACTIVE_PROVIDER != "NSE":
                    for symbol in settings.SYMBOLS:
                        await fetch_and_save(symbol, db)
                        # Gentle delay between symbols to avoid getting rate-limited
                        await asyncio.sleep(2.0)
                else:
                    logger.info("NSE Live Market is closed. Skipping poll cycle fetch.")
                
                # 2. Run 5-minute and 15-minute aggregations in a separate thread
                try:
                    logger.info("Running snapshot aggregations...")
                    await asyncio.to_thread(run_sync_aggregations)
                except Exception as agg_err:
                    logger.exception(f"Unexpected error in aggregation cycle: {str(agg_err)}")
                
                # 3. Evaluate pending InsightOutcomes (check if predictions materialized)
                try:
                    logger.info("Evaluating pending InsightOutcomes...")
                    await asyncio.to_thread(run_sync_outcomes_evaluation)
                except Exception as out_err:
                    logger.exception(f"Unexpected error in outcome evaluation cycle: {str(out_err)}")
                
                # 3.5. Evaluate pending ML target labels retrospectively
                try:
                    logger.info("Evaluating pending ML target labels...")
                    await asyncio.to_thread(run_sync_ml_label_update)
                except Exception as ml_err:
                    logger.exception(f"Unexpected error in ML labels evaluation cycle: {str(ml_err)}")
                
                # 3.7. Evaluate pending Trading Signals outcomes
                try:
                    logger.info("Evaluating pending Trading Signals...")
                    await asyncio.to_thread(run_sync_signals_evaluation)
                except Exception as sig_err:
                    logger.exception(f"Unexpected error in trading signals evaluation cycle: {str(sig_err)}")
                
                # 3.8. Evaluate pending Manual Trader Decisions outcomes
                try:
                    logger.info("Evaluating pending Manual Trader Decisions...")
                    await asyncio.to_thread(run_sync_manual_decisions_evaluation)
                except Exception as md_err:
                    logger.exception(f"Unexpected error in manual decisions evaluation cycle: {str(md_err)}")

                # 3.9. Evaluate pending Observation Log outcomes
                try:
                    logger.info("Evaluating pending Observation Logs...")
                    await asyncio.to_thread(run_sync_observation_logs_evaluation)
                except Exception as ol_err:
                    logger.exception(f"Unexpected error in observation logs evaluation cycle: {str(ol_err)}")
                
                # 4. Run database retention pruner hourly in a separate thread
                now = datetime.utcnow()
                if not last_prune_time or (now - last_prune_time).total_seconds() >= 3600:
                    try:
                        logger.info("Triggering database retention pruner...")
                        await asyncio.to_thread(run_sync_pruner)
                        last_prune_time = now
                    except Exception as prune_err:
                        logger.exception(f"Unexpected error in database pruner cycle: {str(prune_err)}")
                        
            finally:
                db.close()
        except Exception as loop_err:
            logger.exception(f"Unexpected error in background crawler loop execution: {str(loop_err)}")
        finally:
            logger.info(f"Crawler poll cycle complete. Sleeping for {settings.POLL_INTERVAL_SECONDS} seconds...")
            await asyncio.sleep(settings.POLL_INTERVAL_SECONDS)

