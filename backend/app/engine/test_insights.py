import unittest
from datetime import datetime, timedelta
from app.engine.insights import compute_market_state

class TestInsightsEngine(unittest.TestCase):
    def setUp(self):
        self.now = datetime.utcnow()
        self.spot_prev = 24000.0
        self.oi_prev = 1000000
        self.vol_prev = 5000000

    def test_time_gap_threshold(self):
        # Gap > 30 minutes (1801 seconds) should default to NEUTRAL, LOW strength
        timestamp_prev = self.now - timedelta(seconds=1801)
        state, strength = compute_market_state(
            spot_curr=24100.0,
            spot_prev=self.spot_prev,
            oi_curr=1100000,
            oi_prev=self.oi_prev,
            vol_curr=6000000,
            vol_prev=self.vol_prev,
            timestamp_curr=self.now,
            timestamp_prev=timestamp_prev
        )
        self.assertEqual(state, "NEUTRAL")
        self.assertEqual(strength, "LOW")

    def test_long_buildup_high_strength(self):
        # Price Up (+1% = 240 pts) and OI Up (+10% = 100k contracts) within 1 minute
        timestamp_prev = self.now - timedelta(seconds=60)
        state, strength = compute_market_state(
            spot_curr=24240.0, # +1.0% (>= 0.05%)
            spot_prev=self.spot_prev,
            oi_curr=1100000,   # +10.0% (>= 2.0%)
            oi_prev=self.oi_prev,
            vol_curr=6000000,
            vol_prev=self.vol_prev,
            timestamp_curr=self.now,
            timestamp_prev=timestamp_prev
        )
        self.assertEqual(state, "LONG BUILD-UP")
        self.assertEqual(strength, "HIGH")

    def test_short_buildup_medium_strength(self):
        # Price Down (-0.02% = 4.8 pts) and OI Up (+0.8%) within 1 minute
        timestamp_prev = self.now - timedelta(seconds=60)
        state, strength = compute_market_state(
            spot_curr=23995.0, # -0.02% (<= -0.01% but > -0.05%)
            spot_prev=self.spot_prev,
            oi_curr=1008000,   # +0.8% (>= 0.5% but < 2.0%)
            oi_prev=self.oi_prev,
            vol_curr=5100000,
            vol_prev=self.vol_prev,
            timestamp_curr=self.now,
            timestamp_prev=timestamp_prev
        )
        self.assertEqual(state, "SHORT BUILD-UP")
        self.assertEqual(strength, "MEDIUM")

    def test_short_covering_low_strength(self):
        # Price Up (+0.005%) and OI Down (-0.1%) within 1 minute
        timestamp_prev = self.now - timedelta(seconds=60)
        state, strength = compute_market_state(
            spot_curr=24001.0, # +0.004% (< 0.01%)
            spot_prev=self.spot_prev,
            oi_curr=999000,    # -0.1% (> -0.5%)
            oi_prev=self.oi_prev,
            vol_curr=5010000,
            vol_prev=self.vol_prev,
            timestamp_curr=self.now,
            timestamp_prev=timestamp_prev
        )
        self.assertEqual(state, "SHORT COVERING")
        self.assertEqual(strength, "LOW")

    def test_long_unwinding_high_strength(self):
        # Price Down (-0.5%) and OI Down (-3%) within 1 minute
        timestamp_prev = self.now - timedelta(seconds=60)
        state, strength = compute_market_state(
            spot_curr=23880.0, # -0.5% (<= -0.05%)
            spot_prev=self.spot_prev,
            oi_curr=970000,    # -3.0% (<= -2.0%)
            oi_prev=self.oi_prev,
            vol_curr=5500000,
            vol_prev=self.vol_prev,
            timestamp_curr=self.now,
            timestamp_prev=timestamp_prev
        )
        self.assertEqual(state, "LONG UNWINDING")
        self.assertEqual(strength, "HIGH")

if __name__ == "__main__":
    unittest.main()
