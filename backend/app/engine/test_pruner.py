import unittest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.session import Base
from app.db.models import (
    OptionChainSnapshot, OptionChainStrike,
    OptionChainSnapshot5m, OptionChainStrike5m,
    RawProviderResponse, AnalyticsSnapshot, GeneratedInsight
)
from app.engine.aggregator import run_retention_pruner

class TestRetentionPruner(unittest.TestCase):
    def setUp(self):
        # Create an in-memory SQLite DB for testing
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_retention_pruning_and_safety_guard(self):
        now = datetime.utcnow()
        
        # 1. Create raw responses
        db_raw_old = RawProviderResponse(timestamp=now - timedelta(days=8), provider="NSE", symbol="NIFTY", payload_json="{}")
        db_raw_new = RawProviderResponse(timestamp=now - timedelta(days=2), provider="NSE", symbol="NIFTY", payload_json="{}")
        
        # 2. Create 1m snapshots (cutoff is 7 days)
        # NIFTY old (should be deleted)
        snap_1m_old = OptionChainSnapshot(timestamp=now - timedelta(days=8), symbol="NIFTY", expiry_date="2026-06-25", spot_price=24000.0, provider="NSE", collection_status="SUCCESS")
        # NIFTY new (should be kept)
        snap_1m_new = OptionChainSnapshot(timestamp=now - timedelta(days=2), symbol="NIFTY", expiry_date="2026-06-25", spot_price=24005.0, provider="NSE", collection_status="SUCCESS")
        
        # BANKNIFTY 1m snapshot 10 days old - but it's the LATEST successful one for BANKNIFTY (must be protected by safety guard!)
        snap_banknifty_latest_but_old = OptionChainSnapshot(timestamp=now - timedelta(days=10), symbol="BANKNIFTY", expiry_date="2026-06-25", spot_price=52000.0, provider="NSE", collection_status="SUCCESS")
        
        # 3. Create 5m snapshots (cutoff is 30 days)
        # 5m old (should be deleted)
        snap_5m_old = OptionChainSnapshot5m(timestamp=now - timedelta(days=35), symbol="NIFTY", expiry_date="2026-06-25", spot_price=23900.0, provider="NSE", collection_status="SUCCESS")
        # 5m new (should be kept)
        snap_5m_new = OptionChainSnapshot5m(timestamp=now - timedelta(days=15), symbol="NIFTY", expiry_date="2026-06-25", spot_price=23950.0, provider="NSE", collection_status="SUCCESS")
        
        self.db.add_all([db_raw_old, db_raw_new, snap_1m_old, snap_1m_new, snap_banknifty_latest_but_old, snap_5m_old, snap_5m_new])
        self.db.commit()
        
        # 4. Create child strikes
        strike_1m_old = OptionChainStrike(snapshot_id=snap_1m_old.id, strike=24000.0)
        strike_1m_new = OptionChainStrike(snapshot_id=snap_1m_new.id, strike=24000.0)
        strike_bn = OptionChainStrike(snapshot_id=snap_banknifty_latest_but_old.id, strike=52000.0)
        strike_5m_old = OptionChainStrike5m(snapshot_id=snap_5m_old.id, strike=24000.0)
        strike_5m_new = OptionChainStrike5m(snapshot_id=snap_5m_new.id, strike=24000.0)
        
        # 5. Create child analytics snapshots
        anal_1m_old = AnalyticsSnapshot(timestamp=snap_1m_old.timestamp, symbol="NIFTY", source_snapshot_id=snap_1m_old.id, current_spot=24000.0)
        anal_1m_new = AnalyticsSnapshot(timestamp=snap_1m_new.timestamp, symbol="NIFTY", source_snapshot_id=snap_1m_new.id, current_spot=24005.0)
        anal_bn = AnalyticsSnapshot(timestamp=snap_banknifty_latest_but_old.timestamp, symbol="BANKNIFTY", source_snapshot_id=snap_banknifty_latest_but_old.id, current_spot=52000.0)
        
        self.db.add_all([strike_1m_old, strike_1m_new, strike_bn, strike_5m_old, strike_5m_new, anal_1m_old, anal_1m_new, anal_bn])
        self.db.commit()

        # Cache IDs locally before pruning to avoid ObjectDeletedError
        raw_old_id = db_raw_old.id
        raw_new_id = db_raw_new.id
        snap_1m_old_id = snap_1m_old.id
        snap_1m_new_id = snap_1m_new.id
        snap_bn_id = snap_banknifty_latest_but_old.id
        strike_1m_old_id = strike_1m_old.id
        strike_1m_new_id = strike_1m_new.id
        strike_bn_id = strike_bn.id
        anal_1m_old_id = anal_1m_old.id
        anal_1m_new_id = anal_1m_new.id
        anal_bn_id = anal_bn.id
        snap_5m_old_id = snap_5m_old.id
        snap_5m_new_id = snap_5m_new.id

        # Run retention pruner
        run_retention_pruner(self.db)
        
        # Check raw responses
        self.assertIsNone(self.db.query(RawProviderResponse).filter(RawProviderResponse.id == raw_old_id).first())
        self.assertIsNotNone(self.db.query(RawProviderResponse).filter(RawProviderResponse.id == raw_new_id).first())
        
        # Check 1m snapshots
        self.assertIsNone(self.db.query(OptionChainSnapshot).filter(OptionChainSnapshot.id == snap_1m_old_id).first())
        self.assertIsNotNone(self.db.query(OptionChainSnapshot).filter(OptionChainSnapshot.id == snap_1m_new_id).first())
        # BANKNIFTY must NOT be deleted even though it is > 7 days old
        self.assertIsNotNone(self.db.query(OptionChainSnapshot).filter(OptionChainSnapshot.id == snap_bn_id).first())
        
        # Check cascade delete of strikes
        self.assertIsNone(self.db.query(OptionChainStrike).filter(OptionChainStrike.id == strike_1m_old_id).first())
        self.assertIsNotNone(self.db.query(OptionChainStrike).filter(OptionChainStrike.id == strike_1m_new_id).first())
        self.assertIsNotNone(self.db.query(OptionChainStrike).filter(OptionChainStrike.id == strike_bn_id).first())
        
        # Check analytics deletions
        self.assertIsNone(self.db.query(AnalyticsSnapshot).filter(AnalyticsSnapshot.id == anal_1m_old_id).first())
        self.assertIsNotNone(self.db.query(AnalyticsSnapshot).filter(AnalyticsSnapshot.id == anal_1m_new_id).first())
        self.assertIsNotNone(self.db.query(AnalyticsSnapshot).filter(AnalyticsSnapshot.id == anal_bn_id).first())

        # Check 5m snapshots
        self.assertIsNone(self.db.query(OptionChainSnapshot5m).filter(OptionChainSnapshot5m.id == snap_5m_old_id).first())
        self.assertIsNotNone(self.db.query(OptionChainSnapshot5m).filter(OptionChainSnapshot5m.id == snap_5m_new_id).first())
