import unittest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.session import Base
from app.db.models import (
    OptionChainSnapshot, OptionChainStrike,
    OptionChainSnapshot5m, OptionChainStrike5m, AnalyticsSnapshot5m
)
from app.engine.aggregator import aggregate_snapshots

class TestAggregationEngine(unittest.TestCase):
    def setUp(self):
        # Create an in-memory SQLite DB for testing
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_5m_aggregation_rules(self):
        # Base time for testing
        base_time = datetime(2026, 6, 19, 10, 0, 0)

        # Create 5 mock 1-minute snapshots to represent the interval [10:00, 10:05)
        # We check a specific strike: 24000.0
        # Call data values per minute:
        # Min 0 (10:00): OI = 1000, Change OI = 100,  Volume = 5000, IV = 12.5, LTP = 150.0
        # Min 1 (10:01): OI = 1050, Change OI = 150,  Volume = 6000, IV = 12.6, LTP = 152.0
        # Min 2 (10:02): OI = 1030, Change OI = 130,  Volume = 7000, IV = 12.4, LTP = 151.0
        # Min 3 (10:03): OI = 1100, Change OI = 200,  Volume = 8500, IV = 12.8, LTP = 155.0
        # Min 4 (10:04): OI = 1110, Change OI = 210,  Volume = 9000, IV = 12.7, LTP = 156.0
        #
        # Because Change OI and Volume are cumulative session-level fields in NSE:
        # - OI -> Last Value = 1110
        # - Change OI -> Last Value = 210 (not sum)
        # - Volume -> Last Value = 9000 (not sum)
        # - LTP -> Last Value = 156.0
        # - IV -> Average = (12.5 + 12.6 + 12.4 + 12.8 + 12.7) / 5 = 12.6

        for i in range(5):
            ts = base_time + timedelta(minutes=i)
            snap = OptionChainSnapshot(
                timestamp=ts,
                symbol="NIFTY",
                expiry_date="2026-06-25",
                spot_price=24000.0 + i, # spot price close/last
                provider="NSE",
                collection_status="SUCCESS",
                collection_duration_ms=45
            )
            self.db.add(snap)
            self.db.commit()

            strike = OptionChainStrike(
                snapshot_id=snap.id,
                strike=24000.0,
                put_oi=800,
                put_change_oi=50,
                put_volume=4000,
                put_iv=14.0,
                put_ltp=120.0
            )

            # Assign values matching our chronological minutes
            if i == 0:
                strike.call_oi, strike.call_change_oi, strike.call_volume, strike.call_iv, strike.call_ltp = 1000, 100, 5000, 12.5, 150.0
            elif i == 1:
                strike.call_oi, strike.call_change_oi, strike.call_volume, strike.call_iv, strike.call_ltp = 1050, 150, 6000, 12.6, 152.0
            elif i == 2:
                strike.call_oi, strike.call_change_oi, strike.call_volume, strike.call_iv, strike.call_ltp = 1030, 130, 7000, 12.4, 151.0
            elif i == 3:
                strike.call_oi, strike.call_change_oi, strike.call_volume, strike.call_iv, strike.call_ltp = 1100, 200, 8500, 12.8, 155.0
            elif i == 4:
                strike.call_oi, strike.call_change_oi, strike.call_volume, strike.call_iv, strike.call_ltp = 1110, 210, 9000, 12.7, 156.0

            self.db.add(strike)
            self.db.commit()

        # Run aggregation
        aggregate_snapshots(self.db, 5)

        # Query the aggregated snapshot stamped at 10:05
        agg_snap = self.db.query(OptionChainSnapshot5m).filter(
            OptionChainSnapshot5m.timestamp == datetime(2026, 6, 19, 10, 5, 0)
        ).first()

        self.assertIsNotNone(agg_snap)
        self.assertEqual(agg_snap.spot_price, 24004.0) # Close spot price in interval

        # Query the aggregated strike 24000.0
        agg_strike = self.db.query(OptionChainStrike5m).filter(
            OptionChainStrike5m.snapshot_id == agg_snap.id,
            OptionChainStrike5m.strike == 24000.0
        ).first()

        self.assertIsNotNone(agg_strike)
        self.assertEqual(agg_strike.call_oi, 1110) # Last value
        self.assertEqual(agg_strike.call_change_oi, 210) # Last value (verifying no double counting)
        self.assertEqual(agg_strike.call_volume, 9000) # Last value (verifying no double counting)
        self.assertEqual(agg_strike.call_ltp, 156.0) # Last value
        self.assertAlmostEqual(agg_strike.call_iv, 12.6, places=4) # Average of all 5 minutes

        # Check that analytics were also generated for this 5m snapshot
        agg_analytics = self.db.query(AnalyticsSnapshot5m).filter(
            AnalyticsSnapshot5m.source_snapshot_id == agg_snap.id
        ).first()
        self.assertIsNotNone(agg_analytics)
        self.assertEqual(agg_analytics.current_spot, 24004.0)
        self.assertGreater(agg_analytics.pcr, 0.0)
