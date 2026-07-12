import json
import unittest
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import MLFeatureSnapshot
from app.db.session import Base, get_db
from app.main import app


class TestMissionControlAPI(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

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

    def test_overview_empty_database_is_read_only_research_os(self):
        response = self.client.get("/api/mission-control/overview")
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["product"]["name"], "OI Lens Mission Control")
        self.assertEqual(payload["product"]["mode"], "READ_ONLY_RESEARCH")
        self.assertFalse(payload["guardrails"]["can_modify_trading_logic"])
        self.assertFalse(payload["guardrails"]["can_place_live_trades"])
        self.assertTrue(payload["guardrails"]["requires_human_approval"])
        self.assertIn("dataset_health", payload["scores"])
        self.assertIn("replay", payload)
        self.assertIn("pattern_intelligence", payload)
        self.assertIn("rule_audit", payload)
        self.assertIn("execution_intelligence", payload)
        self.assertIn("knowledge_graph", payload)
        self.assertIn("ai_cto", payload)
        self.assertIn("training_forecast", payload)
        self.assertIn("auto_repair", payload)
        self.assertGreaterEqual(len(payload["evidence"]), 1)

    def test_dataset_findings_generate_evidence_and_recommendations(self):
        self.db.add_all(
            [
                MLFeatureSnapshot(
                    timestamp=datetime.utcnow() - timedelta(minutes=10),
                    market_date="2026-07-07",
                    timeframe="1m",
                    symbol="NIFTY",
                    expiry_date="09-Jul-2026",
                    data_quality_score=55,
                    feature_flags=json.dumps({"has_iv": False, "has_pcr": False}),
                    feature_schema_version="v1",
                    engine_version="features-v1",
                    dataset_version="research-v1",
                    average_iv=0.0,
                    pcr=None,
                    label_quality="INCOMPLETE",
                    status="PENDING",
                ),
                MLFeatureSnapshot(
                    timestamp=datetime.utcnow(),
                    market_date="2026-07-07",
                    timeframe="1m",
                    symbol="NIFTY",
                    expiry_date="09-Jul-2026",
                    data_quality_score=65,
                    feature_flags=json.dumps({"has_iv": False, "has_pcr": True}),
                    feature_schema_version="v2",
                    engine_version="features-v2",
                    dataset_version="research-v2",
                    average_iv=0.0,
                    pcr=1.1,
                    label_quality="FULL",
                    status="COMPLETED",
                ),
            ]
        )
        self.db.commit()

        response = self.client.get("/api/mission-control/overview?symbol=NIFTY&market_date=2026-07-07")
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        metrics = payload["dataset"]
        self.assertEqual(metrics["total_samples"], 2)
        self.assertEqual(metrics["missing_iv_pct"], 100.0)
        self.assertEqual(metrics["version_groups"], 2)
        self.assertTrue(any(item["metric"] == "missing_iv_pct" for item in payload["evidence"]))
        self.assertTrue(any("IV" in item["title"] for item in payload["recommendations"]))
        self.assertTrue(any(item["production_mutation_allowed"] is False for item in payload["experiments"]["experiments"]))
        self.assertEqual(payload["training_forecast"]["first_model_name"], "Pattern Direction Model v1")
        self.assertGreaterEqual(payload["auto_repair"]["summary"]["total_actions"], 1)

    def test_constitution_endpoint_exposes_human_approval_gate(self):
        response = self.client.get("/api/mission-control/constitution")
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        keys = {check["key"] for check in payload["checks"]}
        self.assertIn("no_live_trading_mutation", keys)
        self.assertIn("human_approval_gate", keys)
        self.assertGreaterEqual(payload["score"], 80.0)

    def test_stage_two_three_endpoints_are_available(self):
        endpoints = [
            "/api/mission-control/replay-intelligence",
            "/api/mission-control/pattern-intelligence",
            "/api/mission-control/rule-audit",
            "/api/mission-control/execution-intelligence",
            "/api/mission-control/training-forecast",
            "/api/mission-control/auto-repair",
        ]
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, 200)
            self.assertIn("status", response.json())

    def test_auto_repair_dry_run_never_modifies_raw_or_trading_logic(self):
        response = self.client.post("/api/mission-control/auto-repair/dry-run")
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["mode"], "DRY_RUN")
        self.assertIn("No production trading logic or raw market data was modified", payload["message"])


if __name__ == "__main__":
    unittest.main()
