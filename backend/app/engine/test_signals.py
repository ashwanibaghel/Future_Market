import unittest
import json
from datetime import datetime, timedelta
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.session import Base
from app.db.models import OptionChainSnapshot, OptionChainStrike, AnalyticsSnapshot, MLFeatureSnapshot, TradingSignal
from app.api.signals import get_signals_stats
from app.engine.signals import (
    calculate_daily_options_vwap,
    generate_trading_signal,
    score_options_volume_pcr,
    score_pcr_trend,
)
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

        prev_strike = OptionChainStrike(
            snapshot_id=prev_snap.id,
            strike=25000.0,
            call_oi=100,
            put_oi=100,
            call_volume=50,
            put_volume=50,
        )
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
            pcr=0.9, # pcr down (bullish trend)
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
        # The previous immutable strike was inserted with volume to lower daily VWAP.
        # Now VWAP = (24950 * 100 + 25020 * 200) / 300 = 24996.67
        # Spot (25020) > VWAP (24996.67) => True!

        signal = generate_trading_signal(self.db, curr_snap.id)
        self.assertIsNotNone(signal)
        self.assertEqual(signal.signal_type, "BUY_CALL")
        self.assertEqual(signal.suggested_strike, "25000 CE")
        self.assertEqual(signal.strike_selection_reason, "ATM")
        self.assertEqual(signal.signal_version, "v2")
        self.assertGreaterEqual(signal.matched_conditions, 70)
        self.assertEqual(int(round(signal.bullish_score)), signal.matched_conditions)
        self.assertGreater(signal.decision_margin, 0.0)
        self.assertEqual(signal.lifecycle_state, "CREATED")
        self.assertEqual(signal.expected_strength, "Exceptional Setup")
        self.assertIsNone(signal.closest_failed_rule)
        
        # Verify MarketRegime table was populated
        from app.db.models import MarketRegime
        regime = self.db.query(MarketRegime).filter(MarketRegime.symbol == "NIFTY").first()
        self.assertIsNotNone(regime)
        self.assertEqual(regime.trend, "TRENDING")

    def test_generate_trading_signal_no_trade_with_failed_rule(self):
        now = datetime.utcnow()
        curr_snap = OptionChainSnapshot(
            timestamp=now,
            symbol="NIFTY",
            expiry_date="2026-06-25",
            spot_price=25000.0,
            collection_status="SUCCESS"
        )
        self.db.add(curr_snap)
        self.db.commit()

        curr_strike = OptionChainStrike(snapshot_id=curr_snap.id, strike=25000.0, call_volume=10, put_volume=10, call_oi=10, put_oi=10)
        self.db.add(curr_strike)
        
        curr_analytics = AnalyticsSnapshot(
            source_snapshot_id=curr_snap.id,
            pcr=1.0,
            market_state="NEUTRAL",
            strength="LOW"
        )
        self.db.add(curr_analytics)
        self.db.commit()

        with patch(
            "app.engine.patterns.capture_pattern_observation",
            side_effect=RuntimeError("research engine unavailable"),
        ):
            signal = generate_trading_signal(self.db, curr_snap.id)
        self.assertIsNotNone(signal)
        self.assertEqual(signal.signal_type, "NO_TRADE")
        self.assertEqual(signal.expected_strength, "Weak Setup")
        self.assertEqual(signal.closest_failed_rule, "PCR Trend Bias")
        self.assertEqual(
            json.loads(signal.signal_inputs)["engine_features"]["pattern_id"],
            "UNCLASSIFIED",
        )

    def test_generate_trading_signal_v25_calibrated_bullish(self):
        now = datetime(2026, 7, 6, 4, 0)
        snap = OptionChainSnapshot(
            timestamp=now,
            symbol="NIFTY",
            expiry_date="09-Jul-2026",
            spot_price=25020.0,
            collection_status="SUCCESS"
        )
        self.db.add(snap)
        self.db.commit()

        curr_strike = OptionChainStrike(
            snapshot_id=snap.id, strike=25000.0, call_volume=100, put_volume=100, call_oi=100, put_oi=100,
            call_delta=0.0, put_delta=0.0
        )
        self.db.add(curr_strike)
        
        curr_analytics = AnalyticsSnapshot(
            source_snapshot_id=snap.id,
            pcr=1.1,
            market_state="LONG BUILD-UP",
            strength="HIGH"
        )
        self.db.add(curr_analytics)
        self.db.commit()

        sig_v2 = generate_trading_signal(self.db, snap.id, version="v2")
        sig_v25 = generate_trading_signal(self.db, snap.id, version="v2.5")

        self.assertIsNotNone(sig_v2)
        self.assertIsNotNone(sig_v25)
        self.assertEqual(sig_v2.signal_version, "v2")
        self.assertEqual(sig_v25.signal_version, "v2.5")
        self.assertEqual(sig_v2.feature_version, "v2.0")
        self.assertEqual(sig_v25.feature_version, "v2.5")

        v2_inputs = json.loads(sig_v2.signal_inputs)
        v25_inputs = json.loads(sig_v25.signal_inputs)
        self.assertEqual(v2_inputs["engine_features"]["dataset_version"], "v2.0")
        self.assertEqual(v25_inputs["engine_features"]["dataset_version"], "v2.5")
        self.assertEqual(v2_inputs["raw_features"]["market_session"], "Opening")
        self.assertEqual(v2_inputs["raw_features"]["days_to_expiry"], 3)

    def test_pcr_direction_is_symmetric_and_version_is_validated(self):
        self.assertEqual(score_options_volume_pcr(0.5), (10.0, 0.0))
        self.assertEqual(score_options_volume_pcr(1.6), (0.0, 10.0))
        self.assertEqual(score_pcr_trend(-0.1, 0.1), (10.0, 0.0, 1.0))
        self.assertEqual(score_pcr_trend(0.1, 0.1), (0.0, 10.0, 1.0))

        with self.assertRaises(ValueError):
            generate_trading_signal(self.db, 1, version="v3")

    def test_signal_stats_feature_distribution_does_not_crash(self):
        signal = TradingSignal(
            snapshot_id=1,
            timestamp=datetime.utcnow(),
            symbol="NIFTY",
            expiry_date="09-Jul-2026",
            spot_price=25000.0,
            signal_type="BUY_CALL",
            matched_conditions=75,
            total_conditions=100,
            reasons=json.dumps({
                "VWAP Distance": {"contribution": 10.0},
                "EMA Trends": {"contribution": 8.0},
                "PCR Trend": {"contribution": 5.0},
                "OI Change": {"contribution": 7.0, "raw": "delta_oi=2.0%, accel=0.5%"},
            }),
            signal_inputs=json.dumps({
                "raw_features": {
                    "pcr": 0.9,
                    "volume_z_score": 1.5,
                    "net_delta_bias": 0.2,
                }
            }),
            market_state="LONG BUILD-UP",
            signal_version="v2",
            bullish_score=75.0,
            bearish_score=20.0,
            outcome_15m="WIN",
            outcome_30m="WIN",
            outcome_60m="WIN",
            status="COMPLETED",
        )
        self.db.add(signal)
        self.db.commit()

        stats = get_signals_stats(symbol="NIFTY", version="v2", db=self.db)
        self.assertEqual(stats["feature_distribution"]["pcr"]["count"], 1)
        self.assertEqual(stats["feature_distribution"]["pcr"]["stddev"], 0.0)

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
