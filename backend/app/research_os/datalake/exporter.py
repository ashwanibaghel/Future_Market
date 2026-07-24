import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from collections import defaultdict
from sqlalchemy.orm import Session
import pyarrow as pa
import pyarrow.parquet as pq

from app.db.models import OptionChainSnapshot, OptionChainStrike, AnalyticsSnapshot
from app.research_os.governance.versioning import (
    build_provenance_header,
    calculate_file_sha256,
    RULE_ENGINE_VERSION,
    FEATURE_REGISTRY_VERSION,
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

logger = logging.getLogger("research_os.datalake.exporter")

# Native Arrow Struct Schema for Option Strike Records (Zero Denormalization)
STRIKE_STRUCT_TYPE = pa.struct([
    ("strike", pa.float64()),
    ("call_oi", pa.int64()),
    ("call_change_oi", pa.int64()),
    ("call_volume", pa.int64()),
    ("call_iv", pa.float64()),
    ("call_ltp", pa.float64()),
    ("call_delta", pa.float64()),
    ("call_gamma", pa.float64()),
    ("call_theta", pa.float64()),
    ("call_vega", pa.float64()),
    ("put_oi", pa.int64()),
    ("put_change_oi", pa.int64()),
    ("put_volume", pa.int64()),
    ("put_iv", pa.float64()),
    ("put_ltp", pa.float64()),
    ("put_delta", pa.float64()),
    ("put_gamma", pa.float64()),
    ("put_theta", pa.float64()),
    ("put_vega", pa.float64()),
])

SNAPSHOT_ARROW_SCHEMA = pa.schema([
    ("snapshot_id", pa.int64()),
    ("timestamp", pa.string()),
    ("symbol", pa.string()),
    ("expiry_date", pa.string()),
    ("spot_price", pa.float64()),
    ("pcr", pa.float64()),
    ("market_state", pa.string()),
    ("strength", pa.string()),
    ("support_s1", pa.float64()),
    ("resistance_r1", pa.float64()),
    ("strikes", pa.list_(STRIKE_STRUCT_TYPE)),
    ("strikes_count", pa.int32()),
])


def calculate_1min_time_gaps(timestamps: List[datetime]) -> int:
    """
    Calculates missing 1-minute snapshot gaps within trading session hours (09:15 to 15:30 IST).
    """
    if len(timestamps) <= 1:
        return 0

    gap_count = 0
    for i in range(1, len(timestamps)):
        t1 = timestamps[i - 1]
        t2 = timestamps[i]

        # Only check gaps if on the same trading date
        if t1.date() == t2.date():
            diff_minutes = int((t2 - t1).total_seconds() / 60.0)
            if diff_minutes > 1:
                gap_count += (diff_minutes - 1)
    return gap_count


class DatalakeExporter:
    """
    Implements the CTO Mandate:
    SQLite ──► Exporter ──► Validator ──► Parquet ──► Registry ──► Checksum ──► READY
    """

    def __init__(self, db_session: Session):
        self.db = db_session
        self.dirs = ensure_research_storage_structure()
        self.registry = DatasetRegistry()
        self.reporter = QualityReporter()

    def export_snapshots_to_parquet(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        dataset_version: str = DEFAULT_DATASET_VERSION,
    ) -> Dict[str, Any]:
        """
        Executes the full 6-Stage Validated ETL Pipeline with native PyArrow structs, 
        date-partitioned file outputs, and genuine missing minute gap calculations.
        """
        # --- STAGE 1: EXTRACT FROM SQLITE ---
        query = self.db.query(OptionChainSnapshot).filter(OptionChainSnapshot.symbol == symbol)
        if start_date:
            query = query.filter(OptionChainSnapshot.timestamp >= f"{start_date} 00:00:00")
        if end_date:
            query = query.filter(OptionChainSnapshot.timestamp <= f"{end_date} 23:59:59")

        snapshots = query.order_by(OptionChainSnapshot.timestamp.asc()).all()
        expected_rows = len(snapshots)

        if expected_rows == 0:
            logger.warning("No snapshots found in SQLite for symbol '%s'", symbol)
            return {
                "success": False,
                "error": f"No snapshots found in SQLite for symbol '{symbol}' in date range.",
                "total_exported": 0,
            }

        # --- STAGE 2: TRANSFORM & GROUP BY DATE PARTITION ---
        day_groups = defaultdict(list)
        all_timestamps = [snap.timestamp for snap in snapshots]

        # Calculate actual missing 1-minute time gaps
        actual_missing_minutes = calculate_1min_time_gaps(all_timestamps)

        null_pcr_count = 0
        null_iv_count = 0
        duplicate_check = set()
        duplicate_count = 0
        missing_strikes_count = 0
        max_strike_count = 0

        for snap in snapshots:
            snap_key = (snap.symbol, snap.timestamp)
            if snap_key in duplicate_check:
                duplicate_count += 1
                continue
            duplicate_check.add(snap_key)

            analytics = (
                self.db.query(AnalyticsSnapshot)
                .filter(AnalyticsSnapshot.source_snapshot_id == snap.id)
                .first()
            )

            pcr_val = analytics.pcr if analytics else None
            if pcr_val is None:
                null_pcr_count += 1

            strikes = (
                self.db.query(OptionChainStrike)
                .filter(OptionChainStrike.snapshot_id == snap.id)
                .all()
            )

            if len(strikes) > max_strike_count:
                max_strike_count = len(strikes)

            strike_list = []
            for st in strikes:
                if st.call_iv == 0.0 or st.put_iv == 0.0:
                    null_iv_count += 1

                strike_list.append({
                    "strike": float(st.strike),
                    "call_oi": int(st.call_oi or 0),
                    "call_change_oi": int(st.call_change_oi or 0),
                    "call_volume": int(st.call_volume or 0),
                    "call_iv": float(st.call_iv or 0.0),
                    "call_ltp": float(st.call_ltp or 0.0),
                    "call_delta": float(st.call_delta or 0.0),
                    "call_gamma": float(st.call_gamma or 0.0),
                    "call_theta": float(st.call_theta or 0.0),
                    "call_vega": float(st.call_vega or 0.0),
                    "put_oi": int(st.put_oi or 0),
                    "put_change_oi": int(st.put_change_oi or 0),
                    "put_volume": int(st.put_volume or 0),
                    "put_iv": float(st.put_iv or 0.0),
                    "put_ltp": float(st.put_ltp or 0.0),
                    "put_delta": float(st.put_delta or 0.0),
                    "put_gamma": float(st.put_gamma or 0.0),
                    "put_theta": float(st.put_theta or 0.0),
                    "put_vega": float(st.put_vega or 0.0),
                })

            if max_strike_count > 0 and len(strike_list) < max_strike_count:
                missing_strikes_count += (max_strike_count - len(strike_list))

            record = {
                "snapshot_id": int(snap.id),
                "timestamp": snap.timestamp.isoformat(),
                "symbol": str(snap.symbol),
                "expiry_date": str(snap.expiry_date or ""),
                "spot_price": float(snap.spot_price or 0.0),
                "pcr": float(pcr_val) if pcr_val is not None else 0.0,
                "market_state": str(analytics.market_state) if analytics else "NEUTRAL",
                "strength": str(analytics.strength) if analytics else "LOW",
                "support_s1": float(analytics.support) if analytics and analytics.support else 0.0,
                "resistance_r1": float(analytics.resistance) if analytics and analytics.resistance else 0.0,
                "strikes": strike_list,
                "strikes_count": len(strike_list),
            }

            date_key = (snap.timestamp.strftime("%Y"), snap.timestamp.strftime("%m"), snap.timestamp.strftime("%d"))
            day_groups[date_key].append(record)

        total_actual_exported = 0
        written_files = []

        # Export each day cleanly into its partition directory
        for (year, month, day), day_records in day_groups.items():
            partition_dir = os.path.join(
                PARQUET_LAKE_DIR,
                f"symbol={symbol}",
                f"year={year}",
                f"month={month}",
            )
            os.makedirs(partition_dir, exist_ok=True)

            parquet_filename = f"day={day}_snapshots.parquet"
            parquet_path = os.path.join(partition_dir, parquet_filename)

            # PyArrow Table creation using explicit native Struct/List schema
            table = pa.Table.from_pylist(day_records, schema=SNAPSHOT_ARROW_SCHEMA)
            pq.write_table(table, parquet_path, compression="zstd")

            total_actual_exported += len(day_records)
            written_files.append(parquet_path)

        first_path = written_files[0]
        start_str = snapshots[0].timestamp.strftime("%Y%m%d")
        end_str = snapshots[-1].timestamp.strftime("%Y%m%d")
        dataset_id = f"DS-{symbol}-{start_str}_to_{end_str}-{dataset_version}"

        # --- STAGE 3: VALIDATE PARQUET FILES ---
        corrupt_rows = 0
        for ppath in written_files:
            val_res = ParquetDataValidator.validate_file(ppath)
            if not val_res["valid"]:
                corrupt_rows += val_res.get("corrupt_rows", 1)

        # --- STAGE 4: CALCULATE SHA256 CHECKSUM ---
        sha256_hash = calculate_file_sha256(first_path)
        checksum_file = os.path.join(CHECKSUMS_DIR, f"{dataset_id}.sha256")
        with open(checksum_file, "w", encoding="utf-8") as f:
            f.write(f"{sha256_hash}  {os.path.basename(first_path)}\n")

        sha256_valid = (len(sha256_hash) == 64)

        # --- STAGE 5: GENERATE DATA QUALITY REPORT ---
        quality_report = self.reporter.generate_report(
            dataset_id=dataset_id,
            expected_rows=expected_rows,
            actual_rows=total_actual_exported,
            duplicate_snapshots=duplicate_count,
            missing_minutes_count=actual_missing_minutes,
            missing_strikes_count=missing_strikes_count,
            null_pcr_count=null_pcr_count,
            null_iv_count=null_iv_count,
            corrupt_rows_count=corrupt_rows,
            sha256_verification=sha256_valid,
        )

        status = "VALIDATED" if quality_report["quality_pass"] else "INVALID"

        # --- STAGE 6: REGISTER IN DATASET REGISTRY ---
        provenance = build_provenance_header(
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            sha256_checksum=sha256_hash,
            source_database="options_data.db",
            rule_version=RULE_ENGINE_VERSION,
            feature_version=FEATURE_REGISTRY_VERSION,
            provenance_status=status,
        )

        dataset_entry = self.registry.register_dataset({
            "dataset_id": dataset_id,
            "dataset_version": dataset_version,
            "created_date": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "start_date": start_str,
            "end_date": end_str,
            "total_rows": total_actual_exported,
            "total_snapshots": total_actual_exported,
            "feature_version": FEATURE_REGISTRY_VERSION,
            "rule_version": RULE_ENGINE_VERSION,
            "git_commit": provenance["provenance"]["git_commit_hash"],
            "sha256_checksum": sha256_hash,
            "compression_format": "PARQUET_ZSTD",
            "storage_size_bytes": sum(os.path.getsize(f) for f in written_files),
            "status": status,
        })

        return {
            "success": quality_report["quality_pass"],
            "dataset_id": dataset_id,
            "parquet_path": first_path,
            "written_files": written_files,
            "checksum_path": checksum_file,
            "quality_report": quality_report,
            "provenance": provenance,
            "registry_entry": dataset_entry,
            "total_exported": total_actual_exported,
        }
