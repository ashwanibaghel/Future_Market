import unittest
import json
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.session import Base
from app.db.models import OptionChainSnapshot, OptionChainStrike, AnalyticsSnapshot, MLFeatureSnapshot, TradingSignal
from app.engine.signals import calculate_daily_options_vwap, generate_trading_signal
from app.engine.outcomes import evaluate_trading_signals, get_success_threshold_points

class TestSignalEngine(unittest.TestCase):
    def setUp(self):
        # In-memory SQLite for testing
        self.engine = create_engine("sqlite:///:memory:")
        TestingSessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = TestingSessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_daily_options_vwap(self):
        # Create mock snapshots and strikes for VWAP calculation
        now = datetime.utcnow()
        snap1 = OptionChainSnapshot(
            timestamp=now - timedelta(minutes=10),
            symbol="NIFTY",
            expiry_date="2026-06-25",
            spot_price=25000.0,
            collection_status="SUCCESS"
        )
        self.db.add(snap1)
        self.db.commit()
        
        strike1 = OptionChainStrike(
            snapshot_id=snap1.id,
            strike=25000.0,
            call_volume=100,
            put_volume=150
        )
        self.db.add(strike1)
        self.db.commit()

        snap2 = OptionChainSnapshot(
            timestamp=now,
            symbol="NIFTY",
            expiry_date="2026-06-25",
            spot_price=25100.0,
            collection_status="SUCCESS"
        )
        self.db.add(snap2)
        self.db.commit()

        strike2 = OptionChainStrike(
            snapshot_id=snap2.id,
            strike=25100.0,
            call_volume=200,
            put_volume=300
        )
        self.db.add(strike2)
        self.db.commit()

        # Expected VWAP = (25000 * 250 + 25100 * 500) / 750 = 25066.67
        vwap = calculate_daily_options_vwap(self.db, "NIFTY", now)
        self.assertAlmostEqual(vwap, 25066.6666666, places=4)

    def test_generate_trading_signal_bullish(self):
        now = datetime.utcnow()
        # Pre-requisite snapshots
        prev_snap = OptionChainSnapshot(
            timestamp=now - timedelta(minutes=5),
            symbol="NIFTY",
            expiry_date="2026-06-25",
            spot_price=24950.0,
            collection_status="SUCCESS"
        )
        self.db.add(prev_snap)
        self.db.commit()

        prev_strike = OptionChainStrike(snapshot_id=prev_snap.id, strike=25000.0, call_oi=100, put_oi=100)
        self.db.add(prev_strike)
        prev_analytics = AnalyticsSnapshot(source_snapshot_id=prev_snap.id, pcr=1.0, market_state="NEUTRAL", strength="LOW")
        self.db.add(prev_analytics)
        self.db.commit()

        curr_snap = OptionChainSnapshot(
            timestamp=now,
            symbol="NIFTY",
            expiry_date="2026-06-25",
            spot_price=25020.0,
            collection_status="SUCCESS"
        )
        self.db.add(curr_snap)
        self.db.commit()

        curr_strike = OptionChainStrike(snapshot_id=curr_snap.id, strike=25000.0, call_volume=100, put_volume=100, call_oi=110, put_oi=120)
        self.db.add(curr_strike)
        
        curr_analytics = AnalyticsSnapshot(
            source_snapshot_id=curr_snap.id,
            pcr=1.1, # pcr up
            market_state="LONG BUILD-UP", # market state bullish
            strength="HIGH" # strength high
        )
        self.db.add(curr_analytics)
        
        ml_feature = MLFeatureSnapshot(
            source_snapshot_id=curr_snap.id,
            timeframe="1m",
            symbol="NIFTY",
            expiry_date="2026-06-25",
            days_to_expiry=2,
            minutes_from_open=10,
            minutes_to_close=360,
            session_phase="OPENING",
            day_type="NORMAL",
            data_quality_score=100,
            snapshot_age_seconds=1.0,
            feature_flags="{}",
            ema20=24980.0, # spot 25020 > ema20
            ema50=24950.0
        )
        self.db.add(ml_feature)
        self.db.commit()

        # Daily Options VWAP will be 25020 since only 1 snap has volume
        # Spot (25020) > VWAP (25020) is False. Wait! In signals.py:
        # above_vwap is (current_spot > vwap). Since 25020 is not > 25020, we can add a previous snap with volume to ensure Spot > VWAP.
        # Let's override VWAP by adding a previous snapshot with lower spot and volume
        prev_strike.call_volume = 50
        prev_strike.put_volume = 50
        self.db.commit()
        # Now VWAP = (24950 * 100 + 25020 * 200) / 300 = 24996.67
        # Spot (25020) > VWAP (24996.67) => True!

        signal = generate_trading_signal(self.db, curr_snap.id)
        self.assertIsNotNone(signal)
        self.assertEqual(signal.signal_type, "BUY_CALL")
        self.assertEqual(signal.suggested_strike, "25000 CE")
        self.assertEqual(signal.strike_selection_reason, "ATM")
        self.assertEqual(signal.matched_conditions, 6)

    def test_sensex_signal_is_skipped(self):
        now = datetime.utcnow()
        snap = OptionChainSnapshot(
            timestamp=now,
            symbol="SENSEX",
            expiry_date="N/A",
            spot_price=80000.0,
            collection_status="SUCCESS"
        )
        self.db.add(snap)
        self.db.commit()

        # Let's verify no signal is generated
        signal = generate_trading_signal(self.db, snap.id)
        self.assertIsNone(signal)

    def test_evaluate_signals(self):
        now = datetime.utcnow()
        # Generate a BUY_CALL signal
        signal = TradingSignal(
            snapshot_id=1,
            timestamp=now - timedelta(minutes=20),
            symbol="NIFTY",
            expiry_date="2026-06-25",
            spot_price=25000.0,
            signal_type="BUY_CALL",
            suggested_strike="25000 CE",
            matched_conditions=6,
            total_conditions=6,
            reasons="{}",
            market_state="LONG BUILD-UP",
            signal_version="v1",
            status="PENDING"
        )
        self.db.add(signal)
        self.db.commit()

        # Create a successful future snapshot at t+15 mins
        t15_snap = OptionChainSnapshot(
            timestamp=now - timedelta(minutes=20) + timedelta(minutes=15),
            symbol="NIFTY",
            expiry_date="2026-06-25",
            spot_price=25020.0, # +20 points (Threshold is 15.0 for NIFTY) -> WIN!
            collection_status="SUCCESS"
        )
        self.db.add(t15_snap)
        self.db.commit()

        # Run outcomes evaluation
        evaluate_trading_signals(self.db)

        # Refresh from db
        self.db.refresh(signal)
        self.assertEqual(signal.spot_after_15m, 25020.0)
        self.assertEqual(signal.move_15m_points, 20.0)
        self.assertEqual(signal.outcome_15m, "WIN")

if __name__ == "__main__":
    unittest.main()
