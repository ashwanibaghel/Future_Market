import unittest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.session import Base, get_db
from app.db.models import OptionChainSnapshot, OptionChainStrike, AnalyticsSnapshot, InsightOutcome
from app.api.edge_lab import calculate_metrics_for_group

class TestEdgeLabAPI(unittest.TestCase):
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

    def test_insufficient_data_status(self):
        # Request Edge Lab when DB is empty (should return INSUFFICIENT_DATA status for all states)
        response = self.client.get("/api/edge-lab?symbol=NIFTY&timeframe=1m")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(len(data), 4)
        for state_data in data:
            self.assertEqual(state_data["status"], "INSUFFICIENT_DATA")
            self.assertEqual(state_data["samples"], 0)

    def test_helper_metric_calculation(self):
        # Test the helper function directly
        # Seed 20 mock completed outcomes in python memory
        mock_outcomes = []
        for i in range(20):
            # Success is movement > 0. Let's make 15 successes (75% success rate)
            # Spot = 24000. Let's make:
            # 15 successful moves (60m move = +30)
            # 5 failing moves (60m move = -10)
            is_success = i < 15
            move_60 = 30.0 if is_success else -10.0
            
            mock_outcomes.append({
                "movement_15m_points": 10.0 if is_success else -5.0,
                "movement_30m_points": 20.0 if is_success else -8.0,
                "movement_60m_points": move_60,
                "max_favorable_move_60m": 35.0 if is_success else 5.0,
                "max_adverse_move_60m": -5.0 if is_success else -15.0
            })

        res = calculate_metrics_for_group(mock_outcomes, "LONG BUILD-UP")
        
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["samples"], 20)
        self.assertEqual(res["success_60m"], 75.0) # 15/20 = 75%
        self.assertEqual(res["success_15m"], 75.0)
        
        # Avg MFE = (15 * 35 + 5 * 5) / 20 = (525 + 25) / 20 = 27.5
        # Avg MAE = (15 * -5 + 5 * -15) / 20 = (-75 - 75) / 20 = -7.5
        self.assertEqual(res["avg_mfe"], 27.5)
        self.assertEqual(res["avg_mae"], -7.5)
        
        # Median MFE: sorted is fifteen 35s, five 5s. Median of 20 elements is average of 10th and 11th, which are both 35.
        self.assertEqual(res["median_mfe"], 35.0)
        
        # Edge Score: (Success Rate 60m * 0.6) + (Excursion Ratio Score * 0.4)
        # Excursion Ratio = 27.5 / 7.5 = 3.666...
        # Excursion Score = min(100.0, 3.666 * 20.0) = 73.33...
        # Edge Score = (75.0 * 0.6) + (73.333 * 0.4) = 45.0 + 29.333 = 74.333
        self.assertAlmostEqual(res["edge_score"], 74.3, places=1)
        
        # CV & Consistency Score
        # movement list: fifteen 30.0s, five -10.0s
        # Mean = (15 * 30 + 5 * -10)/20 = 400/20 = 20.0
        # Avg absolute move = (15 * 30 + 5 * 10)/20 = 500/20 = 25.0
        # Std Dev of [15 * 30] + [5 * -10]:
        # Variance = (15 * (30-20)^2 + 5 * (-10-20)^2)/20 = (15 * 100 + 5 * 900)/20 = (1500 + 4500)/20 = 6000/20 = 300
        # Sample Std Dev = sqrt(300 * 20 / 19) = sqrt(315.789) = 17.77
        # CV = 17.77 / 25.0 = 0.7108
        # Consistency Score = 100 / (1 + 0.7108) = 58.45%
        self.assertAlmostEqual(res["consistency_score"], 58.5, places=1)
        self.assertEqual(res["confidence"], "LOW") # samples is 20 (LOW confidence tier is 20-50)

    def test_benchmark_sr_endpoint_insufficient(self):
        # Empty DB (should return INSUFFICIENT_DATA)
        response = self.client.get("/api/quant/benchmark-sr?symbol=NIFTY")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "INSUFFICIENT_DATA")
