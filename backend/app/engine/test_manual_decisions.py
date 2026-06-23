import unittest
import json
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.session import Base
from app.db.models import (
    OptionChainSnapshot, OptionChainStrike, AnalyticsSnapshot,
    TradingSignal, ManualTraderDecision, ObservationLog
)
from app.engine.signals import generate_trading_signal
from app.engine.outcomes import (
    evaluate_manual_decisions, evaluate_observation_logs,
    evaluate_trading_signals
)

class TestManualDecisions(unittest.TestCase):
    def setUp(self):
        # In-memory SQLite for testing
        self.engine = create_engine("sqlite:///:memory:")
        TestingSessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = TestingSessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_manual_decision_outcome_bullish_win(self):
        now = datetime.utcnow()
        
        # 1. Create a manual decision (BUY_CALL) at spot = 25000.0
        decision = ManualTraderDecision(
            timestamp=now - timedelta(minutes=20),
            symbol="NIFTY",
            expiry_date="2026-06-25",
            spot_price=25000.0,
            decision_type="BUY_CALL",
            confidence_level="HIGH",
            notes=json.dumps({"technical_bullish": True}),
            status="PENDING"
        )
        self.db.add(decision)
        self.db.commit()
        
        # 2. Create a future snapshot at +15m with spot = 25015.0
        # Success threshold for NIFTY is 15.0 points. +15.0 points => WIN!
        snap_15m = OptionChainSnapshot(
            timestamp=now - timedelta(minutes=20) + timedelta(minutes=15),
            symbol="NIFTY",
            expiry_date="2026-06-25",
            spot_price=25015.0,
            collection_status="SUCCESS"
        )
        self.db.add(snap_15m)
        self.db.commit()
        
        # Run evaluation
        evaluate_manual_decisions(self.db)
        
        # Refresh and verify
        self.db.refresh(decision)
        self.assertEqual(decision.spot_after_15m, 25015.0)
        self.assertEqual(decision.move_15m_points, 15.0)
        self.assertEqual(decision.outcome_15m, "WIN")
        self.assertEqual(decision.status, "PARTIAL")

    def test_observation_log_sync(self):
        now = datetime.utcnow()
        
        # 1. Create a manual decision linked to a manual decision ID
        decision = ManualTraderDecision(
            timestamp=now - timedelta(minutes=20),
            symbol="NIFTY",
            expiry_date="2026-06-25",
            spot_price=25000.0,
            decision_type="BUY_CALL",
            confidence_level="MEDIUM",
            status="PENDING"
        )
        self.db.add(decision)
        self.db.commit()
        self.db.refresh(decision)
        
        # 2. Create the ObservationLog entry
        log_entry = ObservationLog(
            timestamp=now - timedelta(minutes=20),
            symbol="NIFTY",
            spot_price=25000.0,
            market_state="LONG BUILD-UP",
            system_signal="NO_TRADE",
            manual_signal="BUY_CALL",
            manual_decision_id=decision.id,
            status="PENDING"
        )
        self.db.add(log_entry)
        self.db.commit()
        self.db.refresh(log_entry)
        
        # 3. Simulate future snapshot for outcomes evaluation
        snap_15m = OptionChainSnapshot(
            timestamp=now - timedelta(minutes=20) + timedelta(minutes=15),
            symbol="NIFTY",
            expiry_date="2026-06-25",
            spot_price=24980.0, # -20 points => LOSS for BUY_CALL!
            collection_status="SUCCESS"
        )
        self.db.add(snap_15m)
        self.db.commit()
        
        # Run evaluations
        evaluate_manual_decisions(self.db)
        evaluate_observation_logs(self.db)
        
        # Refresh and check sync
        self.db.refresh(decision)
        self.db.refresh(log_entry)
        
        self.assertEqual(decision.outcome_15m, "LOSS")
        self.assertEqual(log_entry.result_15m, "LOSS")
        self.assertEqual(log_entry.status, "PARTIAL")

if __name__ == "__main__":
    unittest.main()
