import unittest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.db.models import (
    OptionChainSnapshot,
    OptionChainStrike,
    AnalyticsSnapshot,
    InsightOutcome,
    SystemMetadata,
    TradingSignal,
)
from app.engine.outcomes import (
    get_prediction_direction,
    create_pending_outcome,
    evaluate_outcomes,
    backfill_insight_outcomes,
    backfill_trading_signals,
    get_metadata,
    set_metadata
)

class TestOutcomesEngine(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_get_prediction_direction(self):
        self.assertEqual(get_prediction_direction("LONG BUILD-UP"), "BULLISH")
        self.assertEqual(get_prediction_direction("SHORT COVERING"), "BULLISH")
        self.assertEqual(get_prediction_direction("SHORT BUILD-UP"), "BEARISH")
        self.assertEqual(get_prediction_direction("LONG UNWINDING"), "BEARISH")
        self.assertEqual(get_prediction_direction("NEUTRAL"), "NEUTRAL")
        self.assertEqual(get_prediction_direction("UNKNOWN"), "NEUTRAL")

    def test_create_pending_outcome(self):
        base_time = datetime(2026, 6, 19, 10, 0, 0)
        snapshot = OptionChainSnapshot(
            id=1,
            timestamp=base_time,
            symbol="NIFTY",
            expiry_date="2026-06-25",
            spot_price=24000.0,
            provider="NSE",
            collection_status="SUCCESS"
        )
        self.db.add(snapshot)
        self.db.commit()

        # Try neutral buildup (should not create outcome)
        created = create_pending_outcome(self.db, snapshot, "NEUTRAL")
        self.assertFalse(created)
        
        # Try non-neutral buildup
        created = create_pending_outcome(self.db, snapshot, "LONG BUILD-UP")
        self.assertTrue(created)

        # Check outcome details
        outcome = self.db.query(InsightOutcome).filter_by(snapshot_id=snapshot.id).first()
        self.assertIsNotNone(outcome)
        self.assertEqual(outcome.symbol, "NIFTY")
        self.assertEqual(outcome.market_state, "LONG BUILD-UP")
        self.assertEqual(outcome.prediction_direction, "BULLISH")
        self.assertEqual(outcome.spot_at_generation, 24000.0)
        self.assertEqual(outcome.status, "PENDING")

        # Try duplicate (should not create duplicate)
        created_dup = create_pending_outcome(self.db, snapshot, "LONG BUILD-UP")
        self.assertFalse(created_dup)

    def test_evaluate_outcomes(self):
        base_time = datetime(2026, 6, 19, 10, 0, 0)
        
        # 1. Create a snapshot at T0
        snap_t0 = OptionChainSnapshot(
            id=10,
            timestamp=base_time,
            symbol="NIFTY",
            expiry_date="2026-06-25",
            spot_price=24000.0,
            provider="NSE",
            collection_status="SUCCESS"
        )
        self.db.add(snap_t0)
        self.db.commit()

        create_pending_outcome(self.db, snap_t0, "LONG BUILD-UP")

        # 2. Add future snapshots at +5m, +15m, +30m, +60m
        horizons = [
            (5, 24010.0),   # +10 points
            (15, 24025.0),  # +25 points
            (30, 24050.0),  # +50 points
            (60, 24100.0)   # +100 points
        ]
        for mins, spot in horizons:
            snap = OptionChainSnapshot(
                timestamp=base_time + timedelta(minutes=mins),
                symbol="NIFTY",
                expiry_date="2026-06-25",
                spot_price=spot,
                provider="NSE",
                collection_status="SUCCESS"
            )
            self.db.add(snap)
        self.db.commit()

        # Run evaluation
        evaluate_outcomes(self.db)

        # Retrieve outcomes
        outcome = self.db.query(InsightOutcome).filter_by(snapshot_id=snap_t0.id).first()
        self.assertIsNotNone(outcome)
        self.assertEqual(outcome.status, "COMPLETED")
        
        # Check spots
        self.assertEqual(outcome.spot_after_5m, 24010.0)
        self.assertEqual(outcome.spot_after_15m, 24025.0)
        self.assertEqual(outcome.spot_after_30m, 24050.0)
        self.assertEqual(outcome.spot_after_60m, 24100.0)

        # Check points movements
        self.assertEqual(outcome.movement_5m_points, 10.0)
        self.assertEqual(outcome.movement_15m_points, 25.0)
        self.assertEqual(outcome.movement_30m_points, 50.0)
        self.assertEqual(outcome.movement_60m_points, 100.0)

        # Check percentages
        self.assertAlmostEqual(outcome.movement_5m_pct, (10.0 / 24000.0) * 100)
        self.assertAlmostEqual(outcome.movement_60m_pct, (100.0 / 24000.0) * 100)

    def test_backfill_insight_outcomes(self):
        now = datetime.utcnow()
        snapshot = OptionChainSnapshot(
            id=20,
            timestamp=now,
            symbol="NIFTY",
            expiry_date="2026-06-25",
            spot_price=24000.0,
            provider="NSE",
            collection_status="SUCCESS"
        )
        self.db.add(snapshot)
        
        # Setup analytics
        analytics = AnalyticsSnapshot(
            timestamp=now,
            symbol="NIFTY",
            source_snapshot_id=snapshot.id,
            current_spot=24000.0,
            pcr=1.0,
            market_state="SHORT BUILD-UP"
        )
        self.db.add(analytics)
        self.db.commit()

        # Perform backfill
        backfill_insight_outcomes(self.db)

        # Verify outcome was created
        outcome = self.db.query(InsightOutcome).filter_by(snapshot_id=snapshot.id).first()
        self.assertIsNotNone(outcome)
        self.assertEqual(outcome.market_state, "SHORT BUILD-UP")
        self.assertEqual(outcome.prediction_direction, "BEARISH")
        self.assertEqual(outcome.status, "PENDING") # Since no future snapshots are loaded in DB

    def test_excursion_evaluation(self):
        base_time = datetime(2026, 6, 19, 10, 0, 0)
        
        # 1. Create a snapshot at T0
        snap_t0 = OptionChainSnapshot(
            id=30,
            timestamp=base_time,
            symbol="NIFTY",
            expiry_date="2026-06-25",
            spot_price=24000.0,
            provider="NSE",
            collection_status="SUCCESS"
        )
        self.db.add(snap_t0)
        self.db.commit()

        create_pending_outcome(self.db, snap_t0, "LONG BUILD-UP")

        # 2. Add snapshots: T0, T+10 (High), T+20 (Low), T+60 (End)
        snapshots_data = [
            (0, 24000.0),
            (10, 24050.0),
            (20, 23970.0),
            (60, 24020.0)
        ]
        
        for mins, spot in snapshots_data:
            snap = OptionChainSnapshot(
                timestamp=base_time + timedelta(minutes=mins),
                symbol="NIFTY",
                expiry_date="2026-06-25",
                spot_price=spot,
                provider="NSE",
                collection_status="SUCCESS"
            )
            self.db.add(snap)
        self.db.commit()

        # Run evaluation
        evaluate_outcomes(self.db)

        # Retrieve outcomes
        outcome = self.db.query(InsightOutcome).filter_by(snapshot_id=snap_t0.id).first()
        self.assertIsNotNone(outcome)
        self.assertEqual(outcome.status, "COMPLETED")
        
        # Check excursion values
        self.assertEqual(outcome.max_favorable_move_60m, 50.0)
        self.assertEqual(outcome.max_adverse_move_60m, -30.0)
        self.assertEqual(outcome.time_to_mfe_minutes, 10)
        self.assertEqual(outcome.time_to_mae_minutes, 20)

    def test_day_boundary_safety(self):
        base_time = datetime(2026, 6, 19, 15, 20, 0) # 3:20 PM
        
        # T0 snapshot
        snap_t0 = OptionChainSnapshot(
            id=40,
            timestamp=base_time,
            symbol="NIFTY",
            expiry_date="2026-06-25",
            spot_price=24000.0,
            provider="NSE",
            collection_status="SUCCESS"
        )
        self.db.add(snap_t0)
        self.db.commit()

        create_pending_outcome(self.db, snap_t0, "LONG BUILD-UP")

        # Snapshots: same day 3:30 PM (+30 points), next day 9:15 AM (+90 points)
        # Next day should be skipped because of different calendar day date.
        snap_same_day = OptionChainSnapshot(
            timestamp=base_time + timedelta(minutes=10),
            symbol="NIFTY",
            expiry_date="2026-06-25",
            spot_price=24030.0,
            provider="NSE",
            collection_status="SUCCESS"
        )
        snap_next_day = OptionChainSnapshot(
            timestamp=base_time + timedelta(minutes=1060),
            symbol="NIFTY",
            expiry_date="2026-06-25",
            spot_price=24090.0,
            provider="NSE",
            collection_status="SUCCESS"
        )
        self.db.add(snap_same_day)
        self.db.add(snap_next_day)
        self.db.commit()

        # Force age complete (since base_time is in the past, age_seconds is already > 65 minutes)
        # So it will automatically trigger completion during evaluate_outcomes.
        evaluate_outcomes(self.db)

        # Retrieve outcomes
        outcome = self.db.query(InsightOutcome).filter_by(snapshot_id=snap_t0.id).first()
        self.assertIsNotNone(outcome)
        self.assertEqual(outcome.status, "COMPLETED")
        
        # Check excursion values (next day snapshot must be filtered out)
        self.assertEqual(outcome.max_favorable_move_60m, 30.0)
        self.assertEqual(outcome.time_to_mfe_minutes, 10)

    def test_metadata_helpers(self):
        # Default value
        val = get_metadata(self.db, "non_existent_key", "default_val")
        self.assertEqual(val, "default_val")

        # Set and get value
        set_metadata(self.db, "my_key", "my_value")
        val = get_metadata(self.db, "my_key")
        self.assertEqual(val, "my_value")

        # Update and get value
        set_metadata(self.db, "my_key", "updated_value")
        val = get_metadata(self.db, "my_key")
        self.assertEqual(val, "updated_value")

    def test_backfill_watermark_and_batching(self):
        # 1. Create a series of snapshots and matching analytics
        now = datetime.utcnow()
        for idx in range(1, 6):  # IDs 101 to 105
            snapshot = OptionChainSnapshot(
                id=100 + idx,
                timestamp=now + timedelta(minutes=idx),
                symbol="NIFTY",
                expiry_date="2026-06-25",
                spot_price=24000.0 + idx,
                provider="NSE",
                collection_status="SUCCESS"
            )
            self.db.add(snapshot)
            
            analytics = AnalyticsSnapshot(
                timestamp=now + timedelta(minutes=idx),
                symbol="NIFTY",
                source_snapshot_id=100 + idx,
                current_spot=24000.0 + idx,
                pcr=1.0,
                market_state="LONG BUILD-UP"
            )
            self.db.add(analytics)
        self.db.commit()

        # 2. Run retrospective backfill (1st run)
        # Verify watermark starts empty
        self.assertIsNone(get_metadata(self.db, "last_successful_backfill_snapshot_id"))
        
        backfill_insight_outcomes(self.db)
        
        # Verify watermark is updated to max snapshot ID (105)
        watermark = get_metadata(self.db, "last_successful_backfill_snapshot_id")
        self.assertEqual(watermark, "105")
        
        # Verify duration is recorded
        duration = get_metadata(self.db, "last_backfill_duration_ms")
        self.assertIsNotNone(duration)
        self.assertTrue(int(duration) >= 0)

        # Verify all 5 outcomes were created
        outcomes_count = self.db.query(InsightOutcome).count()
        self.assertEqual(outcomes_count, 5)

        # 3. Add a new snapshot (ID 106)
        new_snapshot = OptionChainSnapshot(
            id=106,
            timestamp=now + timedelta(minutes=6),
            symbol="NIFTY",
            expiry_date="2026-06-25",
            spot_price=24006.0,
            provider="NSE",
            collection_status="SUCCESS"
        )
        self.db.add(new_snapshot)
        new_analytics = AnalyticsSnapshot(
            timestamp=now + timedelta(minutes=6),
            symbol="NIFTY",
            source_snapshot_id=106,
            current_spot=24006.0,
            pcr=1.0,
            market_state="SHORT BUILD-UP"
        )
        self.db.add(new_analytics)
        self.db.commit()

        # 4. Run retrospective backfill again (2nd run)
        backfill_insight_outcomes(self.db)

        # Watermark should now be updated to 106
        watermark2 = get_metadata(self.db, "last_successful_backfill_snapshot_id")
        self.assertEqual(watermark2, "106")

        # Outcomes count should now be 6
        self.assertEqual(self.db.query(InsightOutcome).count(), 6)

    def test_signal_backfill_repairs_both_version_datasets(self):
        snapshot = OptionChainSnapshot(
            id=201,
            timestamp=datetime(2026, 7, 6, 4, 0),
            symbol="NIFTY",
            expiry_date="09-Jul-2026",
            spot_price=25000.0,
            provider="NSE",
            collection_status="SUCCESS",
        )
        self.db.add(snapshot)
        self.db.add(OptionChainStrike(
            snapshot_id=201,
            strike=25000.0,
            call_oi=100,
            put_oi=100,
            call_volume=100,
            put_volume=100,
        ))
        self.db.add(AnalyticsSnapshot(
            timestamp=snapshot.timestamp,
            symbol="NIFTY",
            expiry_date=snapshot.expiry_date,
            source_snapshot_id=201,
            current_spot=25000.0,
            pcr=1.0,
            market_state="NEUTRAL",
            strength="LOW",
        ))
        self.db.commit()

        backfill_trading_signals(self.db)

        versions = {
            row.signal_version
            for row in self.db.query(TradingSignal).filter(TradingSignal.snapshot_id == 201).all()
        }
        self.assertEqual(versions, {"v2", "v2.5"})
        self.assertEqual(get_metadata(self.db, "last_backfilled_signal_snapshot_id_v2"), "201")
        self.assertEqual(get_metadata(self.db, "last_backfilled_signal_snapshot_id_v2_5"), "201")
