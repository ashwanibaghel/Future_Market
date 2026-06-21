import unittest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.session import Base, get_db
from app.db.models import OptionChainSnapshot, OptionChainStrike, AnalyticsSnapshot, GeneratedInsight

class TestQuantConsoleAPI(unittest.TestCase):
    def setUp(self):
        # Create test database with StaticPool to share connection between threads
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        # Override get_db dependency
        def override_get_db():
            try:
                yield self.db
            finally:
                pass
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_quant_console_endpoint(self):
        base_time = datetime(2026, 6, 19, 9, 0, 0)
        
        # 1. Previous Snapshot (10:00)
        snap_prev = OptionChainSnapshot(
            timestamp=base_time,
            symbol="NIFTY",
            expiry_date="2026-06-25",
            spot_price=24000.0,
            provider="NSE",
            collection_status="SUCCESS",
            collection_duration_ms=50
        )
        self.db.add(snap_prev)
        self.db.commit()
        
        strike_prev = OptionChainStrike(
            snapshot_id=snap_prev.id,
            strike=24000.0,
            call_oi=500000,
            call_change_oi=10000,
            call_volume=2000000,
            call_iv=12.0,
            call_ltp=150.0,
            put_oi=500000,
            put_change_oi=10000,
            put_volume=2000000,
            put_iv=12.0,
            put_ltp=150.0
        )
        self.db.add(strike_prev)
        self.db.commit()
        
        anal_prev = AnalyticsSnapshot(
            timestamp=base_time,
            symbol="NIFTY",
            source_snapshot_id=snap_prev.id,
            current_spot=24000.0,
            pcr=1.0,
            market_state="NEUTRAL",
            strength="LOW",
            iv_change=0.0
        )
        self.db.add(anal_prev)
        self.db.commit()

        # 2. Current Snapshot (10:01)
        snap_curr = OptionChainSnapshot(
            timestamp=base_time + timedelta(minutes=1),
            symbol="NIFTY",
            expiry_date="2026-06-25",
            spot_price=24015.0, # +0.0625%
            provider="NSE",
            collection_status="SUCCESS",
            collection_duration_ms=50
        )
        self.db.add(snap_curr)
        self.db.commit()

        strike_curr = OptionChainStrike(
            snapshot_id=snap_curr.id,
            strike=24000.0,
            call_oi=510000,
            call_change_oi=20000,
            call_volume=2100000,
            call_iv=12.1,
            call_ltp=155.0,
            put_oi=515000,
            put_change_oi=25000,
            put_volume=2050000,
            put_iv=12.1,
            put_ltp=145.0
        )
        self.db.add(strike_curr)
        self.db.commit()

        anal_curr = AnalyticsSnapshot(
            timestamp=snap_curr.timestamp,
            symbol="NIFTY",
            source_snapshot_id=snap_curr.id,
            current_spot=24015.0,
            pcr=1.0098,
            market_state="LONG BUILD-UP",
            strength="HIGH",
            iv_change=0.83
        )
        self.db.add(anal_curr)
        self.db.commit()

        # Add mock insights for the current snapshot
        insight = GeneratedInsight(
            timestamp=snap_curr.timestamp,
            symbol="NIFTY",
            category="BUILDUP",
            insight_text="Put OI dominance observed",
            confidence_level="HIGH",
            expiry_date="2026-06-25"
        )
        self.db.add(insight)
        self.db.commit()

        # 3. Hit the endpoint
        response = self.client.get("/api/quant-console?symbol=NIFTY")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["symbol"], "NIFTY")
        
        # Verify Section 1: Current Snapshot
        self.assertEqual(data["current"]["spot_price"], 24015.0)
        self.assertEqual(data["current"]["market_state"], "LONG BUILD-UP")
        self.assertEqual(data["current"]["strength"], "HIGH")
        self.assertEqual(data["current"]["total_oi"], 1025000) # 510000 + 515000
        
        # Verify Section 2: Previous Snapshot & Differences
        self.assertIsNotNone(data["previous"])
        self.assertEqual(data["previous"]["spot_price"], 24000.0)
        self.assertAlmostEqual(data["difference"]["spot_diff_pct"], 0.0625, places=4)
        self.assertAlmostEqual(data["difference"]["oi_diff_pct"], 2.5, places=4)
        
        # Verify Section 3: Rule Explanation
        self.assertIn("LONG BUILD-UP", data["rule_explanation"]["reason"])
        self.assertIn("+0.062%", data["rule_explanation"]["reason"])
        
        # Verify Section 4: Timeline
        self.assertEqual(len(data["timeline"]), 2)
        self.assertEqual(data["timeline"][1]["market_state"], "LONG BUILD-UP")
        self.assertEqual(data["timeline"][1]["insights"], ["Put OI dominance observed"])

    def test_historical_trends_endpoint(self):
        base_time = datetime(2026, 6, 19, 9, 0, 0)
        
        # Add mock snapshot
        snap = OptionChainSnapshot(
            timestamp=base_time,
            symbol="NIFTY",
            expiry_date="2026-06-25",
            spot_price=24000.0,
            provider="NSE",
            collection_status="SUCCESS",
            collection_duration_ms=50
        )
        self.db.add(snap)
        self.db.commit()
        
        # Add mock strike
        strike = OptionChainStrike(
            snapshot_id=snap.id,
            strike=24000.0,
            call_oi=500000,
            call_change_oi=10000,
            call_volume=2000000,
            call_iv=12.0,
            call_ltp=150.0,
            put_oi=500000,
            put_change_oi=10000,
            put_volume=2000000,
            put_iv=12.0,
            put_ltp=150.0
        )
        self.db.add(strike)
        self.db.commit()
        
        # Add mock analytics
        anal = AnalyticsSnapshot(
            timestamp=base_time,
            symbol="NIFTY",
            source_snapshot_id=snap.id,
            current_spot=24000.0,
            pcr=1.0,
            market_state="NEUTRAL",
            strength="LOW",
            iv_change=0.0,
            support=23900.0,
            resistance=24100.0
        )
        self.db.add(anal)
        self.db.commit()
        
        # Hit endpoint
        response = self.client.get("/api/historical-trends?symbol=NIFTY")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["symbol"], "NIFTY")
        self.assertEqual(data["expiry_date"], "2026-06-25")
        self.assertEqual(len(data["trends"]), 1)
        self.assertEqual(data["trends"][0]["spot_price"], 24000.0)
        self.assertEqual(data["trends"][0]["pcr"], 1.0)
        self.assertEqual(data["trends"][0]["total_call_oi"], 500000)
        self.assertEqual(data["trends"][0]["total_put_oi"], 500000)
        self.assertEqual(data["trends"][0]["average_iv"], 12.0)
        self.assertEqual(data["trends"][0]["support"], 23900.0)
        self.assertEqual(data["trends"][0]["resistance"], 24100.0)

