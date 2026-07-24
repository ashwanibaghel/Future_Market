import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from app.research_os.datalake.reader import DuckDBDataReader
from app.research_os.replay.clock import ReplayClock
from app.research_os.replay.context import BlindSnapshotContext
from app.research_os.replay.harness import SimulationHarness, SimulatedSignalRecord, SimulationRunResult
from app.research_os.governance.dataset_registry import EXPERIMENT_REGISTRY_DIR, ensure_research_storage_structure

logger = logging.getLogger("research_os.replay.engine")


class ReplayEngine:
    """
    Core Minute-by-Minute Historical Replay Engine.
    Executes simulations with mathematical temporal isolation guarantees.
    """

    def __init__(self, data_reader: Optional[DuckDBDataReader] = None):
        ensure_research_storage_structure()
        self.reader = data_reader or DuckDBDataReader()
        self.harness = SimulationHarness()

    def run_simulation(
        self,
        symbol: str,
        year: Optional[str] = None,
        month: Optional[str] = None,
        run_id_prefix: str = "SIM",
    ) -> SimulationRunResult:
        """
        Executes a deterministic historical simulation for a given symbol and time partition.
        """
        # 1. Fetch historical partition records
        raw_snapshots = self.reader.query_snapshots(symbol=symbol, year=year, month=month, limit=50000)
        if not raw_snapshots:
            logger.warning("No Parquet snapshots found for symbol=%s, year=%s, month=%s", symbol, year, month)
            return SimulationRunResult(
                run_id=f"{run_id_prefix}-EMPTY",
                symbol=symbol,
                start_time="",
                end_time="",
                total_ticks_evaluated=0,
                signals_generated_count=0,
                buy_call_count=0,
                buy_put_count=0,
                no_trade_count=0,
                signal_records=[],
            )

        # 2. Extract and sort unique timestamps
        dt_list = []
        for s in raw_snapshots:
            try:
                dt_list.append(datetime.fromisoformat(s["timestamp"]))
            except Exception:
                continue

        unique_dts = sorted(list(set(dt_list)))
        if not unique_dts:
            raise ValueError("Failed to parse valid timestamps for replay engine.")

        # 3. Initialize ReplayClock
        clock = ReplayClock(unique_dts)

        # 4. Minute-by-minute simulation loop with BlindSnapshotContext
        signal_records: List[SimulatedSignalRecord] = []
        buy_call_count = 0
        buy_put_count = 0
        no_trade_count = 0

        logger.info("Starting ReplayEngine simulation across %d ticks (%s to %s)", len(unique_dts), clock.current_time, unique_dts[-1])

        while True:
            current_time = clock.current_time
            # Spawn isolated context for this exact tick
            context = BlindSnapshotContext(current_time=current_time, data_reader=self.reader)
            
            # Evaluate tick via harness
            record = self.harness.evaluate_tick(context, symbol=symbol)
            signal_records.append(record)

            if record.decision == "BUY_CALL":
                buy_call_count += 1
            elif record.decision == "BUY_PUT":
                buy_put_count += 1
            else:
                no_trade_count += 1

            if clock.is_finished():
                break
            clock.advance()

        start_iso = unique_dts[0].isoformat()
        end_iso = unique_dts[-1].isoformat()
        run_id = f"{run_id_prefix}-{symbol}-{unique_dts[0].strftime('%Y%m%d')}"

        result = SimulationRunResult(
            run_id=run_id,
            symbol=symbol,
            start_time=start_iso,
            end_time=end_iso,
            total_ticks_evaluated=len(unique_dts),
            signals_generated_count=buy_call_count + buy_put_count,
            buy_call_count=buy_call_count,
            buy_put_count=buy_put_count,
            no_trade_count=no_trade_count,
            signal_records=signal_records,
        )

        # 5. Persist simulation result artifact
        self._persist_run_artifact(result)
        logger.info("ReplayEngine simulation complete. Generated %d signals out of %d ticks.", result.signals_generated_count, result.total_ticks_evaluated)
        return result

    def _persist_run_artifact(self, result: SimulationRunResult):
        """Saves simulation run summary artifact as JSON."""
        artifact_path = os.path.join(EXPERIMENT_REGISTRY_DIR, f"{result.run_id}.json")
        data = {
            "run_id": result.run_id,
            "symbol": result.symbol,
            "start_time": result.start_time,
            "end_time": result.end_time,
            "total_ticks_evaluated": result.total_ticks_evaluated,
            "signals_generated_count": result.signals_generated_count,
            "buy_call_count": result.buy_call_count,
            "buy_put_count": result.buy_put_count,
            "no_trade_count": result.no_trade_count,
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        with open(artifact_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
