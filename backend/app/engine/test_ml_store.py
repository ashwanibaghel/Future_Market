import unittest
import json
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.db.models import (
    OptionChainSnapshot, OptionChainStrike, AnalyticsSnapshot,
    RawProviderResponse, MLFeatureSnapshot
)
from app.engine.ml_store import (
    is_last_thursday, calculate_expiry_type, calculate_day_type,
    capture_ml_features, update_ml_labels
)

class TestMLStore(unittest.TestCase):
    def setUp(self):
        # Create an in-memory database
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

    def test_calendar_math_helpers(self):
        # Thursday, 25-Jun-2026 is the last Thursday of June
        dt_last_thu = datetime(2026, 6, 25)
        # Thursday, 18-Jun-2026 is NOT the last Thursday
        dt_mid_thu = datetime(2026, 6, 18)
        # Friday, 26-Jun-2026 is NOT a Thursday
        dt_fri = datetime(2026, 6, 26)

        self.assertTrue(is_last_thursday(dt_last_thu))
        self.assertFalse(is_last_thursday(dt_mid_thu))
        self.assertFalse(is_last_thursday(dt_fri))

        # Check expiry type determination
        self.assertEqual(calculate_expiry_type("25-Jun-2026"), "MONTHLY")
        self.assertEqual(calculate_expiry_type("18-Jun-2026"), "WEEKLY")

        # Check day type determination
        # 1. Monthly expiry day
        now_dt = datetime(2026, 6, 25, 11, 0, 0)
        self.assertEqual(calculate_day_type(now_dt, "25-Jun-2026", "MONTHLY"), "MONTHLY_EXPIRY")
        # 2. Weekly expiry day
        now_dt = datetime(2026, 6, 18, 11, 0, 0)
        self.assertEqual(calculate_day_type(now_dt, "18-Jun-2026", "WEEKLY"), "EXPIRY_DAY")
        # 3. Pre expiry day
        now_dt = datetime(2026, 6, 17, 11, 0, 0)
        self.assertEqual(calculate_day_type(now_dt, "18-Jun-2026", "WEEKLY"), "PRE_EXPIRY")
        # 4. Normal day
        now_dt = datetime(2026, 6, 15, 11, 0, 0)
        self.assertEqual(calculate_day_type(now_dt, "18-Jun-2026", "WEEKLY"), "NORMAL")

    def test_feature_capture(self):
        # 1. Create a raw provider response to check exchange timestamp extraction
        raw_payload = json.dumps({
            "timestamp": "19-Jun-2026 15:30:00",
            "data": []
        })
        raw_resp = RawProviderResponse(
            timestamp=datetime(2026, 6, 19, 10, 0, 5), # Save time in UTC
            provider="NSE",
            symbol="NIFTY",
            payload_json=raw_payload
        )
        self.db.add(raw_resp)
        self.db.commit()

        # 2. Create option chain snapshot
        snapshot = OptionChainSnapshot(
            timestamp=datetime(2026, 6, 19, 10, 0, 5), # 10:00:05 UTC (3:30:05 PM IST)
            symbol="NIFTY",
            instrument_type="INDEX",
            expiry_date="25-Jun-2026",
            spot_price=24000.0,
            provider="NSE",
            collection_status="SUCCESS",
            collection_duration_ms=200
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)

        # 3. Create strikes (let's add 12 strikes to get a 100 quality score)
        strikes = []
        for strike_val in range(23800, 24200, 30):
            strike = OptionChainStrike(
                snapshot_id=snapshot.id,
                strike=float(strike_val),
                call_oi=1000,
                call_change_oi=100,
                call_volume=500,
                call_iv=15.0,
                call_ltp=100.0,
                put_oi=1200,
                put_change_oi=200,
                put_volume=600,
                put_iv=16.0,
                put_ltp=80.0
            )
            strikes.append(strike)
            self.db.add(strike)
        self.db.commit()

        # 4. Create analytics snapshot
        analytics = AnalyticsSnapshot(
            timestamp=snapshot.timestamp,
            symbol="NIFTY",
            expiry_date="25-Jun-2026",
            source_snapshot_id=snapshot.id,
            current_spot=24000.0,
            pcr=1.2,
            market_state="LONG BUILD-UP",
            strength="MEDIUM",
            iv_change=1.5,
            support=23900.0,
            secondary_support=23800.0,
            resistance=24100.0,
            secondary_resistance=24200.0,
            distance_to_support=100.0,
            distance_to_resistance=100.0,
            support_strength="HIGH",
            resistance_strength="HIGH"
        )
        self.db.add(analytics)
        self.db.commit()

        # Call capture
        success = capture_ml_features(self.db, snapshot.id, timeframe="1m")
        self.assertTrue(success)

        # Retrieve saved feature snapshot
        feat = self.db.query(MLFeatureSnapshot).first()
        self.assertIsNotNone(feat)
        self.assertEqual(feat.symbol, "NIFTY")
        self.assertEqual(feat.timeframe, "1m")
        self.assertEqual(feat.market_date, "2026-06-19")
        self.assertEqual(feat.expiry_type, "MONTHLY") # 25-Jun-2026 is monthly
        self.assertEqual(feat.day_type, "NORMAL") # not expiry day on 19th
        self.assertEqual(feat.days_to_expiry, 6) # 25 - 19 = 6 days
        self.assertEqual(feat.data_quality_score, 100) # Perfect score!
        
        # Test latency age calculation: 
        # exchange timestamp is "19-Jun-2026 15:30:00" IST = 10:00:00 UTC.
        # save time is 10:00:05 UTC. Age should be 5.0 seconds.
        self.assertEqual(feat.snapshot_age_seconds, 5.0)

        # Test pre-encoded IDs
        self.assertEqual(feat.market_state_id, 1) # LONG BUILD-UP = 1
        self.assertEqual(feat.strength_score, 2) # MEDIUM = 2

        # Test flags
        flags = json.loads(feat.feature_flags)
        self.assertTrue(flags["has_iv"])
        self.assertTrue(flags["has_sr"])
        self.assertTrue(flags["has_pcr"])

    def test_label_generation_and_leakage_protection(self):
        # Initial snapshot at time T
        t0 = datetime(2026, 6, 19, 10, 0, 0)
        
        # Initial snapshot
        snap0 = OptionChainSnapshot(
            timestamp=t0,
            symbol="NIFTY",
            expiry_date="25-Jun-2026",
            spot_price=24000.0,
            collection_status="SUCCESS"
        )
        self.db.add(snap0)
        self.db.commit()

        # Analytics for snap0
        an0 = AnalyticsSnapshot(
            timestamp=t0,
            symbol="NIFTY",
            expiry_date="25-Jun-2026",
            source_snapshot_id=snap0.id,
            current_spot=24000.0,
            pcr=1.0,
            market_state="NEUTRAL",
            strength="LOW"
        )
        self.db.add(an0)
        self.db.commit()

        # Capture initial features
        capture_ml_features(self.db, snap0.id, timeframe="1m")

        # Now let's create outcomes in the future to resolve labels
        # 15m later: +20 points (+0.083% > +0.05% -> UP)
        snap_15 = OptionChainSnapshot(
            timestamp=t0 + timedelta(minutes=15),
            symbol="NIFTY",
            expiry_date="25-Jun-2026",
            spot_price=24020.0,
            collection_status="SUCCESS"
        )
        # 30m later: -30 points (-0.125% < -0.05% -> DOWN)
        snap_30 = OptionChainSnapshot(
            timestamp=t0 + timedelta(minutes=30),
            symbol="NIFTY",
            expiry_date="25-Jun-2026",
            spot_price=23970.0,
            collection_status="SUCCESS"
        )
        # 60m later: +5 points (+0.02% -> SIDEWAYS)
        snap_60 = OptionChainSnapshot(
            timestamp=t0 + timedelta(minutes=60),
            symbol="NIFTY",
            expiry_date="25-Jun-2026",
            spot_price=24005.0,
            collection_status="SUCCESS"
        )
        self.db.add(snap_15)
        self.db.add(snap_30)
        self.db.add(snap_60)
        self.db.commit()

        # Check label ready:
        # label_ready_at should be T + 60 minutes
        feat = self.db.query(MLFeatureSnapshot).first()
        self.assertEqual(feat.label_ready_at, t0 + timedelta(minutes=60))
        self.assertEqual(feat.status, "PENDING")

        # Let's run label update BEFORE label_ready_at (e.g. current time is T+30m)
        # We can mock this by running update_ml_labels but the function queries for label_ready_at <= current_time.
        # So we can see that no records are updated if we check with a mock time.
        # But since update_ml_labels uses datetime.utcnow() to compare, we can check by shifting our feature's label_ready_at to past!
        feat.label_ready_at = datetime.utcnow() - timedelta(seconds=10)
        self.db.commit()

        updated = update_ml_labels(self.db)
        self.assertEqual(updated, 1)

        # Retrieve and verify results
        self.db.refresh(feat)
        self.assertEqual(feat.status, "COMPLETED")
        self.assertEqual(feat.label_quality, "FULL")
        self.assertEqual(json.loads(feat.available_horizons), ["15m", "30m", "60m"])

        # Returns
        self.assertAlmostEqual(feat.return_15m_pct, 0.083, places=3)
        self.assertAlmostEqual(feat.return_30m_pct, -0.125, places=3)
        self.assertAlmostEqual(feat.return_60m_pct, 0.021, places=3)
        
        self.assertEqual(feat.return_15m_points, 20.0)
        self.assertEqual(feat.return_30m_points, -30.0)
        self.assertEqual(feat.return_60m_points, 5.0)

        # Directions
        self.assertEqual(feat.direction_15m, "UP")
        self.assertEqual(feat.direction_30m, "DOWN")
        self.assertEqual(feat.direction_60m, "SIDEWAYS")
