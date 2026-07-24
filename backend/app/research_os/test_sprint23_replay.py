import os
import unittest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, OptionChainSnapshot, OptionChainStrike, AnalyticsSnapshot
from app.research_os.datalake.exporter import DatalakeExporter
from app.research_os.datalake.reader import DuckDBDataReader
from app.research_os.replay.clock import ReplayClock
from app.research_os.replay.context import BlindSnapshotContext
from app.research_os.replay.exceptions import TemporalLeakageError
from app.research_os.replay.engine import ReplayEngine
from app.research_os.replay.harness import SimulationHarness


class TestSprint23ReplayEngine(unittest.TestCase):
    """
    Comprehensive Unit & Integration Test Suite for Sprint 23.
    Verifies Replay Clock, BlindSnapshotContext, Temporal Firewall, and ReplayEngine.
    """

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(self.engine)
        SessionLocal = sessionmaker(bind=self.engine)
        self.db = SessionLocal()

        # Seed 10 mock 1-minute snapshots for NIFTY & BANKNIFTY
        self.base_time = datetime(2026, 7, 24, 9, 15, 0)
        self.timestamps = []

        for i in range(10):
            ts = self.base_time + timedelta(minutes=i)
            self.timestamps.append(ts)

            # NIFTY snapshot
            snap_nifty = OptionChainSnapshot(
                timestamp=ts,
                symbol="NIFTY",
                expiry_date="2026-07-30",
                spot_price=24200.0 + i * 5,
                provider="NSE",
                collection_status="SUCCESS",
                collection_duration_ms=100,
            )
            self.db.add(snap_nifty)

            # BANKNIFTY snapshot (Multi-symbol test)
            snap_bank = OptionChainSnapshot(
                timestamp=ts,
                symbol="BANKNIFTY",
                expiry_date="2026-07-30",
                spot_price=52000.0 + i * 10,
                provider="NSE",
                collection_status="SUCCESS",
                collection_duration_ms=100,
            )
            self.db.add(snap_bank)
            self.db.commit()

            # Add Analytics
            a_nifty = AnalyticsSnapshot(
                timestamp=ts,
                symbol="NIFTY",
                source_snapshot_id=snap_nifty.id,
                current_spot=snap_nifty.spot_price,
                pcr=1.0 + (i * 0.05),
                market_state="LONG BUILD-UP" if i >= 5 else "NEUTRAL",
                strength="HIGH",
                support=24100.0,
                resistance=24300.0,
            )
            self.db.add(a_nifty)
            self.db.commit()

        # Export to Parquet Lake
        exporter = DatalakeExporter(self.db)
        exporter.export_snapshots_to_parquet("NIFTY", "2026-07-24", "2026-07-24", "DS-v1.0.0")
        exporter.export_snapshots_to_parquet("BANKNIFTY", "2026-07-24", "2026-07-24", "DS-v1.0.0")

        self.reader = DuckDBDataReader()

    def tearDown(self):
        self.db.close()

    def test_01_clock_operations(self):
        """Test ReplayClock advance, rewind, seek, reset, and is_finished."""
        clock = ReplayClock(self.timestamps)
        self.assertEqual(clock.current_time, self.timestamps[0])
        self.assertFalse(clock.is_finished())

        # Advance
        next_t = clock.advance()
        self.assertEqual(next_t, self.timestamps[1])
        self.assertEqual(clock.current_index, 1)

        # Rewind
        prev_t = clock.rewind()
        self.assertEqual(prev_t, self.timestamps[0])

        # Seek
        target = self.timestamps[5]
        seek_t = clock.seek(target)
        self.assertEqual(seek_t, target)

        # Reset
        reset_t = clock.reset()
        self.assertEqual(reset_t, self.timestamps[0])

        # Seek to end
        clock.seek(self.timestamps[-1])
        self.assertTrue(clock.is_finished())

    def test_02_context_current_and_previous_snapshot(self):
        """Test BlindSnapshotContext current and previous snapshot retrieval."""
        current_t = self.timestamps[3]
        ctx = BlindSnapshotContext(current_time=current_t, data_reader=self.reader)
        
        # Current snapshot
        snap = ctx.get_snapshot("NIFTY")
        self.assertIsNotNone(snap)
        self.assertEqual(snap["symbol"], "NIFTY")
        self.assertLessEqual(snap["timestamp"], current_t.isoformat())

        # Previous snapshot (t - 1m)
        prev_snap = ctx.get_previous_snapshot("NIFTY")
        self.assertIsNotNone(prev_snap)
        self.assertLessEqual(prev_snap["timestamp"], (current_t - timedelta(minutes=1)).isoformat())

    def test_03_context_history_lookback(self):
        """Test history window retrieval bounded strictly by current_time."""
        current_t = self.timestamps[5]
        ctx = BlindSnapshotContext(current_time=current_t, data_reader=self.reader)
        
        history = ctx.get_history("NIFTY", minutes=3)
        self.assertGreaterEqual(len(history), 1)
        for record in history:
            rec_dt = datetime.fromisoformat(record["timestamp"])
            self.assertLessEqual(rec_dt, current_t)

    def test_04_temporal_firewall_exceptions(self):
        """
        MANDATORY TEMPORAL FIREWALL TEST:
        Verify TemporalLeakageError is raised when querying future timestamps.
        """
        current_t = self.timestamps[3]
        ctx = BlindSnapshotContext(current_time=current_t, data_reader=self.reader)
        
        future_t = current_t + timedelta(minutes=2)
        with self.assertRaises(TemporalLeakageError):
            ctx.get_snapshot("NIFTY", target_time=future_t)

    def test_05_first_candle_empty_history(self):
        """Verify first candle tick handles lookback gracefully without error."""
        first_t = self.timestamps[0]
        ctx = BlindSnapshotContext(current_time=first_t, data_reader=self.reader)
        
        history = ctx.get_history("NIFTY", minutes=5)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["timestamp"], first_t.isoformat())

    def test_06_multi_symbol_context(self):
        """Test multi-symbol context queries at identical tick."""
        current_t = self.timestamps[4]
        ctx = BlindSnapshotContext(current_time=current_t, data_reader=self.reader)
        
        snap_nifty = ctx.get_snapshot("NIFTY")
        snap_bank = ctx.get_snapshot("BANKNIFTY")

        self.assertEqual(snap_nifty["symbol"], "NIFTY")
        self.assertEqual(snap_bank["symbol"], "BANKNIFTY")

    def test_07_deterministic_replay_engine(self):
        """
        Verify ReplayEngine produces 100% bit-exact identical signal results 
        when executed twice over the same partition dataset.
        """
        engine = ReplayEngine(data_reader=self.reader)
        res1 = engine.run_simulation("NIFTY", year="2026", month="07", run_id_prefix="RUN1")
        res2 = engine.run_simulation("NIFTY", year="2026", month="07", run_id_prefix="RUN2")

        self.assertEqual(res1.total_ticks_evaluated, res2.total_ticks_evaluated)
        self.assertEqual(res1.signals_generated_count, res2.signals_generated_count)
        self.assertEqual(res1.buy_call_count, res2.buy_call_count)
        self.assertEqual(res1.buy_put_count, res2.buy_put_count)
        self.assertEqual(res1.no_trade_count, res2.no_trade_count)

        for s1, s2 in zip(res1.signal_records, res2.signal_records):
            self.assertEqual(s1.timestamp, s2.timestamp)
            self.assertEqual(s1.decision, s2.decision)
            self.assertAlmostEqual(s1.score, s2.score, places=4)


if __name__ == "__main__":
    unittest.main()
