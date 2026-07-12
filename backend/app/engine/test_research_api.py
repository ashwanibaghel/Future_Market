import unittest
import json
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.session import Base, get_db
from app.db.models import MLFeatureSnapshot
from app.engine.ml_store import capture_ml_features

class TestResearchAPI(unittest.TestCase):
    def setUp(self):
        # Create test database with StaticPool
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

    def test_status_empty_db(self):
        response = self.client.get("/api/ml-dataset-status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data["total_samples"], 0)
        self.assertEqual(data["completed_labels"], 0)
        self.assertEqual(data["pending_labels"], 0)
        self.assertEqual(data["label_quality_breakdown"]["FULL"], 0)
        self.assertEqual(data["data_quality_metrics"]["avg_quality_score"], 0.0)
        self.assertEqual(data["research_coverage"]["pattern_observations"], 0)
        self.assertEqual(data["data_quality_metrics"]["duplicate_records"], 0)
        self.assertEqual(data["health_summary"]["status"], "BLOCKED")
        self.assertIn("collection_gaps", data["collection_health"])
        self.assertEqual(data["class_balance"]["15m"]["UP"], 0)

    def test_status_populated_db(self):
        # Seed some data in MLFeatureSnapshot
        rec1 = MLFeatureSnapshot(
            timestamp=datetime.utcnow() - timedelta(hours=2),
            market_date="2026-06-19",
            timeframe="1m",
            symbol="NIFTY",
            expiry_date="25-Jun-2026",
            expiry_type="MONTHLY",
            days_to_expiry=6,
            minutes_from_open=120,
            minutes_to_close=255,
            session_phase="MIDDAY",
            day_type="NORMAL",
            data_quality_score=90,
            snapshot_age_seconds=2.5,
            feature_flags=json.dumps({"has_iv": True, "has_sr": True, "has_pcr": True, "has_order_flow": True}),
            pcr=1.1,
            direction_15m="UP",
            direction_30m="DOWN",
            direction_60m="SIDEWAYS",
            label_quality="FULL",
            status="COMPLETED",
            label_ready_at=datetime.utcnow() - timedelta(hours=1)
        )
        rec2 = MLFeatureSnapshot(
            timestamp=datetime.utcnow(),
            market_date="2026-06-19",
            timeframe="5m",
            symbol="BANKNIFTY",
            expiry_date="25-Jun-2026",
            expiry_type="MONTHLY",
            days_to_expiry=6,
            minutes_from_open=150,
            minutes_to_close=225,
            session_phase="MIDDAY",
            day_type="NORMAL",
            data_quality_score=70,
            snapshot_age_seconds=12.0,
            feature_flags=json.dumps({"has_iv": False, "has_sr": True, "has_pcr": False, "has_order_flow": True}),
            pcr=0.0,
            status="PENDING",
            label_ready_at=datetime.utcnow() + timedelta(hours=1)
        )
        self.db.add(rec1)
        self.db.add(rec2)
        self.db.commit()

        # Check status API
        response = self.client.get("/api/ml-dataset-status")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["total_samples"], 2)
        self.assertEqual(data["completed_labels"], 1)
        self.assertEqual(data["pending_labels"], 1)
        self.assertEqual(data["timeframe_breakdown"]["1m"], 1)
        self.assertEqual(data["timeframe_breakdown"]["5m"], 1)
        self.assertEqual(data["expiry_breakdown"]["MONTHLY"], 2)
        self.assertEqual(data["label_quality_breakdown"]["FULL"], 1)
        
        # Average quality score: (90 + 70) / 2 = 80
        self.assertEqual(data["data_quality_metrics"]["avg_quality_score"], 80.0)
        
        # Missing IV pct: 1 out of 2 has "has_iv": false -> 50%
        self.assertEqual(data["data_quality_metrics"]["missing_iv_pct"], 50.0)
        
        # Class Balance
        self.assertEqual(data["class_balance"]["15m"]["UP"], 1)
        self.assertEqual(data["class_balance"]["30m"]["DOWN"], 1)
        self.assertEqual(data["class_balance"]["60m"]["SIDEWAYS"], 1)
        self.assertIn(data["health_summary"]["status"], ["BLOCKED", "DEGRADED", "READY"])
        self.assertEqual(len(data["health_summary"]["checks"]), 9)

    def test_research_intelligence_api(self):
        rec1 = MLFeatureSnapshot(
            timestamp=datetime.utcnow() - timedelta(days=7),
            market_date="2026-06-15",
            timeframe="1m",
            symbol="NIFTY",
            expiry_date="25-Jun-2026",
            expiry_type="MONTHLY",
            data_quality_score=90,
            feature_flags=json.dumps({"has_iv": True, "has_sr": True, "has_pcr": True}),
            pcr=1.1,
            oi_imbalance=0.2,
            atr=15.0,
            direction_30m="UP",
            return_30m_pct=0.9,
            label_quality="FULL",
            status="COMPLETED",
            label_ready_at=datetime.utcnow() - timedelta(days=7),
        )
        rec2 = MLFeatureSnapshot(
            timestamp=datetime.utcnow(),
            market_date="2026-06-22",
            timeframe="1m",
            symbol="NIFTY",
            expiry_date="25-Jun-2026",
            expiry_type="MONTHLY",
            data_quality_score=70,
            feature_flags=json.dumps({"has_iv": False, "has_sr": True, "has_pcr": True}),
            pcr=1.3,
            oi_imbalance=0.4,
            atr=18.0,
            direction_30m="DOWN",
            return_30m_pct=-0.4,
            status="PENDING",
            label_ready_at=datetime.utcnow() + timedelta(minutes=30),
        )
        self.db.add_all([rec1, rec2])
        self.db.commit()

        response = self.client.get("/api/research/intelligence?symbol=NIFTY")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["label_monitor"]["total"], 2)
        self.assertIn("30m", data["dataset_imbalance"])
        self.assertIn("pcr", data["feature_distribution"])
        self.assertIn("pcr", data["feature_drift"])
        self.assertEqual(data["training_readiness"]["status"], "NOT_READY")
        self.assertIn("training_registry", data["phase_foundations"])

    def test_export_api(self):
        # Seed record
        rec = MLFeatureSnapshot(
            timestamp=datetime.utcnow(),
            market_date="2026-06-19",
            timeframe="15m",
            symbol="NIFTY",
            expiry_date="25-Jun-2026",
            expiry_type="MONTHLY",
            days_to_expiry=6,
            minutes_from_open=180,
            minutes_to_close=195,
            session_phase="MIDDAY",
            day_type="NORMAL",
            data_quality_score=95,
            snapshot_age_seconds=1.5,
            feature_flags=json.dumps({"has_iv": True, "has_sr": True, "has_pcr": True, "has_order_flow": True}),
            pcr=1.05,
            status="COMPLETED",
            label_ready_at=datetime.utcnow() - timedelta(minutes=5)
        )
        self.db.add(rec)
        self.db.commit()

        # Trigger export
        response = self.client.get("/api/ml-dataset-export?symbol=NIFTY&timeframe=15m")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "text/csv; charset=utf-8")
        
        content = response.text
        lines = content.strip().split("\r\n")
        self.assertEqual(len(lines), 2) # header + 1 record row
        
        headers = lines[0].split(",")
        self.assertIn("timeframe", headers)
        self.assertIn("symbol", headers)
        self.assertIn("data_quality_score", headers)

        data_row = lines[1].split(",")
        # find indexes
        timeframe_idx = headers.index("timeframe")
        symbol_idx = headers.index("symbol")
        quality_idx = headers.index("data_quality_score")

        self.assertEqual(data_row[timeframe_idx], "15m")
        self.assertEqual(data_row[symbol_idx], "NIFTY")
        self.assertEqual(data_row[quality_idx], "95")
