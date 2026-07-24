import os
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import pyarrow as pa
import pyarrow.parquet as pq

from app.acquisition.discovery import InstrumentDiscoveryService, INSTRUMENTS_DB_PATH
from app.acquisition.upstox_client import UpstoxApiClient
from app.acquisition.validator import DataQualityAuditor
from app.research_os.governance.versioning import (
    build_provenance_header,
    calculate_file_sha256,
    DEFAULT_DATASET_VERSION,
)
from app.research_os.governance.dataset_registry import (
    DatasetRegistry,
    PARQUET_LAKE_DIR,
    CHECKSUMS_DIR,
    ensure_research_storage_structure,
)
from app.research_os.governance.quality_reporter import QualityReporter
from app.research_os.datalake.validator import ParquetDataValidator

logger = logging.getLogger("acquisition.backfill")

# Arrow Schema for OHLCV Candle Storage
CANDLE_ARROW_SCHEMA = pa.schema([
    ("timestamp", pa.string()),
    ("timestamp_utc", pa.int64()),
    ("instrument_key", pa.string()),
    ("open", pa.float64()),
    ("high", pa.float64()),
    ("low", pa.float64()),
    ("close", pa.float64()),
    ("volume", pa.int64()),
    ("open_interest", pa.int64()),
])


class HistoricalBackfillOrchestrator:
    """
    Executes the 6-Stage Validated Historical Data Backfill Pipeline 
    for any generic trading instrument.
    """

    def __init__(self, upstox_client: Optional[UpstoxApiClient] = None, db_path: str = INSTRUMENTS_DB_PATH):
        ensure_research_storage_structure()
        self.discovery = InstrumentDiscoveryService(db_path)
        self.client = upstox_client or UpstoxApiClient()
        self.registry = DatasetRegistry()
        self.reporter = QualityReporter()

    def backfill_instrument(
        self,
        instrument_key: str,
        start_date: str,
        end_date: str,
        dataset_version: str = DEFAULT_DATASET_VERSION,
    ) -> Dict[str, Any]:
        """
        Executes complete backfill for an instrument across a multi-month date range.
        """
        inst = self.discovery.get_instrument(instrument_key)
        if not inst:
            raise ValueError(f"Instrument key '{instrument_key}' not registered in Instrument Master.")

        # --- STAGE 1: FETCH CANDLES FROM UPSTOX API ---
        logger.info("Stage 1: Fetching 1-minute historical candles for %s (%s to %s)", instrument_key, start_date, end_date)
        candles = self.client.fetch_multi_month_candles(
            instrument_key=instrument_key,
            start_date=start_date,
            end_date=end_date,
            interval="1minute",
        )

        expected_rows = len(candles)
        if expected_rows == 0:
            logger.warning("Zero candles returned for %s", instrument_key)
            return {"success": False, "total_exported": 0, "error": "Zero candles returned"}

        # --- STAGE 2: TRANSFORM & GROUP BY PARTITION ---
        day_groups = defaultdict(list)
        for c in candles:
            # Upstox candle format: [timestamp, open, high, low, close, volume, oi]
            ts_str = c[0]
            dt = datetime.fromisoformat(ts_str)
            ts_utc = int(dt.timestamp())

            record = {
                "timestamp": ts_str,
                "timestamp_utc": ts_utc,
                "instrument_key": instrument_key,
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "volume": int(c[5]) if len(c) > 5 else 0,
                "open_interest": int(c[6]) if len(c) > 6 else 0,
            }

            partition_key = (inst.exchange, instrument_key.replace("|", "_"), dt.strftime("%Y"), dt.strftime("%m"))
            day_groups[partition_key].append(record)

        written_files = []
        total_exported = 0

        for (exch, safe_key, year, month), day_records in day_groups.items():
            partition_dir = os.path.join(
                PARQUET_LAKE_DIR,
                f"exchange={exch}",
                f"instrument_key={safe_key}",
                f"year={year}",
                f"month={month}",
            )
            os.makedirs(partition_dir, exist_ok=True)

            parquet_path = os.path.join(partition_dir, "candles.parquet")
            table = pa.Table.from_pylist(day_records, schema=CANDLE_ARROW_SCHEMA)
            pq.write_table(table, parquet_path, compression="zstd")

            written_files.append(parquet_path)
            total_exported += len(day_records)

        first_path = written_files[0]
        dataset_id = f"DS-{inst.trading_symbol}-{start_date.replace('-', '')}_to_{end_date.replace('-', '')}-{dataset_version}"

        # --- STAGE 3: VALIDATE PARQUET INTEGRITY ---
        corrupt_rows = 0
        for ppath in written_files:
            val_res = ParquetDataValidator.validate_file(ppath)
            if not val_res["valid"]:
                corrupt_rows += val_res.get("corrupt_rows", 1)

        # --- STAGE 4: SHA256 CHECKSUM ---
        sha256_hash = calculate_file_sha256(first_path)
        checksum_file = os.path.join(CHECKSUMS_DIR, f"{dataset_id}.sha256")
        with open(checksum_file, "w", encoding="utf-8") as f:
            f.write(f"{sha256_hash}  {os.path.basename(first_path)}\n")

        # --- STAGE 5: DATA QUALITY AUDIT ---
        audit_res = DataQualityAuditor.audit_candles(instrument_key, candles)
        quality_report = self.reporter.generate_report(
            dataset_id=dataset_id,
            expected_rows=expected_rows,
            actual_rows=total_exported,
            duplicate_snapshots=audit_res["duplicate_count"],
            missing_minutes_count=audit_res["missing_minutes_count"],
            corrupt_rows_count=corrupt_rows,
            sha256_verification=(len(sha256_hash) == 64),
        )

        status = "VALIDATED" if quality_report["quality_pass"] else "INVALID"

        # --- STAGE 6: REGISTER IN DATASET REGISTRY & SYNC HISTORY ---
        provenance = build_provenance_header(
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            sha256_checksum=sha256_hash,
            provenance_status=status,
        )

        self.registry.register_dataset({
            "dataset_id": dataset_id,
            "dataset_version": dataset_version,
            "created_date": datetime.now(timezone.utc).isoformat(),
            "symbol": inst.trading_symbol,
            "start_date": start_date,
            "end_date": end_date,
            "total_rows": total_exported,
            "total_snapshots": total_exported,
            "git_commit": provenance["provenance"]["git_commit_hash"],
            "sha256_checksum": sha256_hash,
            "compression_format": "PARQUET_ZSTD",
            "storage_size_bytes": sum(os.path.getsize(f) for f in written_files),
            "status": status,
        })

        self._record_sync_history(
            sync_id=f"SYNC-{dataset_id}",
            instrument_key=instrument_key,
            sync_type="BACKFILL",
            start_date=start_date,
            end_date=end_date,
            total_candles=total_exported,
            missing_minutes=audit_res["missing_minutes_count"],
            sha256_hash=sha256_hash,
            status=status,
        )

        return {
            "success": quality_report["quality_pass"],
            "dataset_id": dataset_id,
            "instrument_key": instrument_key,
            "total_exported": total_exported,
            "written_files": written_files,
            "checksum_path": checksum_file,
            "quality_report": quality_report,
            "provenance": provenance,
        }

    def _record_sync_history(
        self,
        sync_id: str,
        instrument_key: str,
        sync_type: str,
        start_date: str,
        end_date: str,
        total_candles: int,
        missing_minutes: int,
        sha256_hash: str,
        status: str,
    ):
        """Records synchronization entry in SQLite sync_history table."""
        cursor = self.discovery.conn.cursor()
        cursor.execute("""
        INSERT OR REPLACE INTO sync_history (
            sync_id, instrument_key, sync_type, start_date, end_date,
            total_candles_synced, missing_minutes_detected, sha256_checksum, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (sync_id, instrument_key, sync_type, start_date, end_date, total_candles, missing_minutes, sha256_hash, status))
        self.discovery.conn.commit()
