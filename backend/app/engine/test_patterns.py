import json
import unittest
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import (
    DatasetMetadata,
    FeatureLineage,
    ImmutableSnapshotError,
    MLFeatureSnapshot,
    OptionChainSnapshot,
    OptionChainStrike,
    PatternLibrary,
    PatternObservation,
)
from app.db.session import Base, get_db
from app.engine.patterns import backfill_pattern_observations, capture_pattern_observation
from app.main import app


class TestPatternEngine(unittest.TestCase):
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
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def _seed_snapshot(self, timestamp, spot, total_oi, pcr, ema20=99.0):
        snapshot = OptionChainSnapshot(
            timestamp=timestamp,
            symbol="NIFTY",
            expiry_date="09-Jul-2026",
            spot_price=spot,
            provider="NSE",
            collection_status="SUCCESS",
            collection_duration_ms=125,
        )
        self.db.add(snapshot)
        self.db.flush()

        call_oi = total_oi // 2
        put_oi = total_oi - call_oi
        self.db.add(OptionChainStrike(
            snapshot_id=snapshot.id,
            strike=100.0,
            call_oi=call_oi,
            put_oi=put_oi,
            call_iv=15.0,
            put_iv=16.0,
            call_delta=0.5,
            put_delta=-0.5,
            call_gamma=0.02,
            put_gamma=0.02,
        ))
        self.db.add(MLFeatureSnapshot(
            timestamp=timestamp,
            market_date="2026-07-06",
            timeframe="1m",
            symbol="NIFTY",
            expiry_date="09-Jul-2026",
            expiry_type="WEEKLY",
            source_snapshot_id=snapshot.id,
            source_table="option_chain_snapshots",
            feature_schema_version="v2.0",
            engine_version="features-v2.0",
            dataset_version="research-v1.0",
            days_to_expiry=3,
            minutes_from_open=60,
            minutes_to_close=315,
            session_phase="MIDDAY",
            day_type="NORMAL",
            data_quality_score=100,
            snapshot_age_seconds=0.125,
            feature_flags=json.dumps({
                "has_iv": True,
                "has_sr": True,
                "has_pcr": True,
                "has_order_flow": True,
            }),
            pcr=pcr,
            market_state="LONG BUILD-UP",
            regime_trend="UPTREND",
            ema20=ema20,
            ema50=98.0,
            atr=1.0,
            status="PENDING",
            label_ready_at=timestamp + timedelta(minutes=60),
        ))
        self.db.commit()
        return snapshot

    def test_capture_is_versioned_idempotent_and_traceable(self):
        t0 = datetime(2026, 7, 6, 4, 45)
        first = self._seed_snapshot(t0, 100.0, 1000, 1.0)
        second = self._seed_snapshot(t0 + timedelta(minutes=1), 101.0, 1100, 1.1)
        third = self._seed_snapshot(t0 + timedelta(minutes=2), 102.0, 1200, 1.2)

        obs1 = capture_pattern_observation(self.db, first.id)
        obs2 = capture_pattern_observation(self.db, second.id)
        obs3 = capture_pattern_observation(self.db, third.id)
        duplicate = capture_pattern_observation(self.db, third.id)

        self.assertEqual(obs1.pattern_id, "TrendUp_OIFlat_PCRFlat")
        self.assertEqual(obs2.pattern_id, "TrendUp_OIUp_PCRUp")
        self.assertEqual(obs3.pattern_id, "TrendUp_OIUp_PCRUp")
        self.assertEqual(obs3.pattern_age_snapshots, 2)
        self.assertEqual(duplicate.id, obs3.id)
        self.assertEqual(self.db.query(PatternObservation).count(), 3)
        self.assertEqual(self.db.query(DatasetMetadata).count(), 3)
        self.assertEqual(self.db.query(FeatureLineage).count(), 15)

        library = self.db.query(PatternLibrary).filter(
            PatternLibrary.pattern_id == "TrendUp_OIUp_PCRUp"
        ).one()
        self.assertEqual(library.observed_count, 2)
        self.assertEqual(library.maximum_age_snapshots, 2)
        self.assertGreater(library.average_confidence, 0.0)

        metadata = self.db.query(DatasetMetadata).filter(
            DatasetMetadata.source_snapshot_id == third.id
        ).one()
        self.assertEqual(metadata.timezone, "Asia/Kolkata")
        self.assertEqual(metadata.api_source, "NSE_NEXT_API")
        self.assertEqual(json.loads(metadata.missing_fields), [])

    def test_immutable_market_snapshot_rejects_updates(self):
        snapshot = self._seed_snapshot(datetime(2026, 7, 6, 4, 45), 100.0, 1000, 1.0)
        snapshot.spot_price = 999.0
        with self.assertRaises(ImmutableSnapshotError):
            self.db.commit()
        self.db.rollback()

    def test_historical_backfill_is_chronological_and_idempotent(self):
        t0 = datetime(2026, 7, 6, 4, 45)
        self._seed_snapshot(t0 + timedelta(minutes=1), 101.0, 1100, 1.1)
        self._seed_snapshot(t0, 100.0, 1000, 1.0)

        self.assertEqual(backfill_pattern_observations(self.db), 2)
        self.assertEqual(backfill_pattern_observations(self.db), 0)

        observations = self.db.query(PatternObservation).order_by(
            PatternObservation.timestamp.asc()
        ).all()
        self.assertEqual(len(observations), 2)
        self.assertEqual(observations[0].oi_state, "OIFlat")
        self.assertEqual(observations[1].oi_state, "OIUp")

    def test_pattern_research_apis(self):
        snapshot = self._seed_snapshot(datetime(2026, 7, 6, 4, 45), 100.0, 1000, 1.0)
        observation = capture_pattern_observation(self.db, snapshot.id)

        library_response = self.client.get("/api/patterns/library?symbol=NIFTY")
        self.assertEqual(library_response.status_code, 200)
        self.assertEqual(library_response.json()["count"], 1)

        observations_response = self.client.get("/api/patterns/observations?timeframe=1m")
        self.assertEqual(observations_response.status_code, 200)
        self.assertEqual(observations_response.json()["data"][0]["pattern_version"], "pattern-v1.0")

        lineage_response = self.client.get(
            f"/api/patterns/observations/{observation.id}/lineage"
        )
        self.assertEqual(lineage_response.status_code, 200)
        self.assertEqual(lineage_response.json()["count"], 5)

        metadata_response = self.client.get("/api/dataset-metadata?symbol=NIFTY")
        self.assertEqual(metadata_response.status_code, 200)
        self.assertEqual(metadata_response.json()["data"][0]["dataset_version"], "research-v1.0")

        leaderboard_response = self.client.get("/api/patterns/leaderboard?symbol=NIFTY")
        self.assertEqual(leaderboard_response.status_code, 200)
        self.assertEqual(leaderboard_response.json()["count"], 1)
        self.assertIn("reliability", leaderboard_response.json()["data"][0])

        lifecycle_response = self.client.get("/api/patterns/lifecycles?symbol=NIFTY")
        self.assertEqual(lifecycle_response.status_code, 200)
        self.assertEqual(lifecycle_response.json()["count"], 1)
        self.assertIn("duration_minutes", lifecycle_response.json()["data"][0])

        transition_response = self.client.get("/api/patterns/transitions?symbol=NIFTY")
        self.assertEqual(transition_response.status_code, 200)
        self.assertIn("data", transition_response.json())

        rule_response = self.client.get("/api/patterns/rule-leaderboard?symbol=NIFTY")
        self.assertEqual(rule_response.status_code, 200)
        self.assertGreaterEqual(rule_response.json()["count"], 1)
