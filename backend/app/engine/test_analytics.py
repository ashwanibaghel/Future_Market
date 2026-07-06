import unittest
import json
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.session import Base
from app.db.models import OptionChainSnapshot, OptionChainStrike, AnalyticsSnapshot, MLFeatureSnapshot, TradingSignal, ManualTraderDecision, DailyReport
from app.engine.validation import generate_daily_validation_report, pearson_correlation

class TestAnalyticsEngine(unittest.TestCase):
    def setUp(self):
        # In-memory SQLite for testing
        self.engine = create_engine("sqlite:///:memory:")
        TestingSessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = TestingSessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_pearson_correlation(self):
        x = [1, 2, 3, 4, 5]
        y = [2, 4, 6, 8, 10]
        # Perfect positive correlation
        self.assertEqual(pearson_correlation(x, y), 1.0)
        
        # Perfect negative correlation
        y_neg = [10, 8, 6, 4, 2]
        self.assertEqual(pearson_correlation(x, y_neg), -1.0)
        
        # Empty lists / single values
        self.assertEqual(pearson_correlation([], []), 0.0)
        self.assertEqual(pearson_correlation([1], [2]), 0.0)

    def test_generate_daily_validation_report(self):
        now = datetime.utcnow()
        date_str = now.strftime("%Y-%m-%d")
        
        # 1. Create mock snapshots
        for i in range(5):
            snap = OptionChainSnapshot(
                timestamp=now - timedelta(minutes=(10 - i)),
                symbol="NIFTY",
                expiry_date="2026-07-09",
                spot_price=25000.0,
                collection_status="SUCCESS"
            )
            self.db.add(snap)
            self.db.commit()
            
            strike = OptionChainStrike(
                snapshot_id=snap.id,
                strike=25000.0,
                call_oi=1000,
                put_oi=1000,
                call_volume=10,
                put_volume=10,
                call_delta=0.5, # Greeks present
                put_delta=-0.5
            )
            self.db.add(strike)
            self.db.commit()

        # 2. Add system signals
        # Correctly avoiding NO_TRADE
        sig1 = TradingSignal(
            timestamp=now - timedelta(minutes=5),
            symbol="NIFTY",
            expiry_date="2026-07-09",
            spot_price=25000.0,
            signal_type="NO_TRADE",
            signal_version="v2.5",
            matched_conditions=20,
            total_conditions=100,
            reasons=json.dumps({"EMA Trend": {"contribution": 0.0, "weight": 15.0}}),
            signal_inputs=json.dumps({
                "engine_features": {
                    "pattern_id": "TrendDown_OIDown_PCRUp",
                    "market_phase": "LOW_VOL_RANGING"
                }
            }),
            move_60m_points=5.0, # Flat move, within threshold
            outcome_60m="CORRECT_AVOIDANCE"
        )
        self.db.add(sig1)
        
        # Winning BUY_CALL
        sig2 = TradingSignal(
            timestamp=now - timedelta(minutes=2),
            symbol="NIFTY",
            expiry_date="2026-07-09",
            spot_price=25000.0,
            signal_type="BUY_CALL",
            signal_version="v2.5",
            matched_conditions=85,
            total_conditions=100,
            reasons=json.dumps({"EMA Trend": {"contribution": 15.0, "weight": 15.0}}),
            signal_inputs=json.dumps({
                "engine_features": {
                    "pattern_id": "TrendUp_OIUp_PCRDown",
                    "market_phase": "TRENDING_BULL"
                }
            }),
            move_60m_points=80.0, # Winning move (NIFTY threshold is ~45-50 points)
            outcome_60m="WIN"
        )
        self.db.add(sig2)
        self.db.commit()

        # 3. Add manual decisions
        man1 = ManualTraderDecision(
            timestamp=now - timedelta(minutes=2),
            symbol="NIFTY",
            expiry_date="2026-07-09",
            spot_price=25000.0,
            decision_type="BUY_CALL",
            notes="Matching system",
            outcome_60m="WIN"
        )
        self.db.add(man1)
        self.db.commit()

        # Run report generation
        report = generate_daily_validation_report(self.db, date_str, version="v2.5")
        
        # Assert report exists
        self.assertIsNotNone(report)
        self.assertEqual(report.date, date_str)
        
        # Load and verify JSON contents
        summary = json.loads(report.summary_json)
        
        self.assertEqual(summary["summary"]["total_snapshots"], 5)
        self.assertEqual(summary["summary"]["total_signals"], 2)
        self.assertEqual(summary["summary"]["buy_call_count"], 1)
        self.assertEqual(summary["summary"]["no_trade_count"], 1)
        self.assertEqual(summary["summary"]["system_wins"], 1)
        self.assertEqual(summary["summary"]["correct_avoidances"], 1)
        
        # Confusion matrix checks
        self.assertEqual(summary["confusion_matrix"]["BUY_CALL"]["actual_bullish"], 1)
        self.assertEqual(summary["confusion_matrix"]["NO_TRADE"]["actual_range"], 1)
        
        # Manual vs system checks
        self.assertEqual(summary["manual_vs_system"]["manual_decisions_count"], 1)
        self.assertEqual(summary["manual_vs_system"]["agreement_rate_pct"], 100.0)
        self.assertEqual(summary["manual_vs_system"]["manual_win_rate_pct"], 100.0)
        
        # Data quality checks
        self.assertEqual(summary["data_quality"]["missing_greeks_snapshots"], 0)
        self.assertEqual(summary["data_quality"]["outliers_detected"], 0)
        
        # Verify markdown content contains tables
        self.assertIn("Confusion Matrix", report.markdown_content)
        self.assertIn("Pattern-wise Win Rates", report.markdown_content)
        self.assertIn("TrendUp_OIUp_PCRDown", report.markdown_content)
