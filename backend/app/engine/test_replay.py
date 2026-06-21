import unittest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.session import Base
from app.db.models import OptionChainSnapshot, OptionChainStrike
from app.engine.replay import replay_historical_snapshots

class TestReplayEngine(unittest.TestCase):
    def setUp(self):
        # Create an in-memory SQLite DB for testing
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_replay_historical_snapshots_and_gap_handling(self):
        # Setup mock historical snapshots with a 33-minute gap
        # Chronological order:
        # 1. 09:15: Spot = 24000, OI = 1,000,000, Vol = 5,000,000
        # 2. 09:16: Spot = 24015, OI = 1,025,000, Vol = 5,100,000 (Price Up +0.0625%, OI Up +2.5% -> LONG BUILD-UP, HIGH)
        # 3. 09:17: Spot = 24020, OI = 1,030,000, Vol = 5,150,000 (LONG BUILD-UP)
        # --- GAP (33 minutes) ---
        # 4. 09:50: Spot = 24050, OI = 1,050,000, Vol = 5,300,000 (Gap > 30m -> must reset to NEUTRAL, LOW)
        
        base_time = datetime(2026, 6, 19, 9, 15, 0)
        times = [
            base_time,                              # 09:15
            base_time + timedelta(minutes=1),       # 09:16
            base_time + timedelta(minutes=2),       # 09:17
            base_time + timedelta(minutes=35)       # 09:50 (33 minute gap from 09:17)
        ]

        spots = [24000.0, 24015.0, 24020.0, 24050.0]
        ois = [1000000, 1025000, 1030000, 1050000]
        vols = [5000000, 5100000, 5150000, 5300000]

        for i, ts in enumerate(times):
            snap = OptionChainSnapshot(
                timestamp=ts,
                symbol="NIFTY",
                expiry_date="2026-06-25",
                spot_price=spots[i],
                provider="NSE",
                collection_status="SUCCESS",
                collection_duration_ms=40
            )
            self.db.add(snap)
            self.db.commit()

            # Create strike 24000.0 (assign proportional shares of total OI/volume)
            strike = OptionChainStrike(
                snapshot_id=snap.id,
                strike=24000.0,
                call_oi=ois[i] // 2,
                call_change_oi=10000,
                call_volume=vols[i] // 2,
                call_iv=12.0,
                call_ltp=150.0,
                put_oi=ois[i] // 2,
                put_change_oi=10000,
                put_volume=vols[i] // 2,
                put_iv=12.0,
                put_ltp=150.0
            )
            self.db.add(strike)
            self.db.commit()

        # Run replay
        replay_results = replay_historical_snapshots(
            self.db,
            symbol="NIFTY",
            start_time=base_time - timedelta(minutes=5),
            end_time=base_time + timedelta(minutes=40)
        )

        # We expect 4 replayed states
        self.assertEqual(len(replay_results), 4)

        # 1. Step 1 (09:15) - First step, no previous snapshot -> NEUTRAL
        self.assertEqual(replay_results[0]["market_state"], "NEUTRAL")
        self.assertEqual(replay_results[0]["strength"], "LOW")

        # 2. Step 2 (09:16) - Price +0.0625%, OI +2.5% -> LONG BUILD-UP, HIGH
        self.assertEqual(replay_results[1]["market_state"], "LONG BUILD-UP")
        self.assertEqual(replay_results[1]["strength"], "HIGH")

        # 3. Step 3 (09:17) - Price Up slightly, OI Up slightly -> LONG BUILD-UP
        self.assertEqual(replay_results[2]["market_state"], "LONG BUILD-UP")

        # 4. Step 4 (09:50) - 33-minute gap (>30m) -> Reset to NEUTRAL, LOW
        self.assertEqual(replay_results[3]["market_state"], "NEUTRAL")
        self.assertEqual(replay_results[3]["strength"], "LOW")
        
        # Verify PCR, Support, and Resistance are present
        self.assertAlmostEqual(replay_results[0]["pcr"], 1.0, places=4)
        self.assertEqual(replay_results[0]["support"], 24000.0)
        self.assertEqual(replay_results[0]["resistance"], 24000.0)
