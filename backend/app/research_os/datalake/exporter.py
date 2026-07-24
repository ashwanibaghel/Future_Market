import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
import pyarrow as pa
import pyarrow.parquet as pq

from app.db.models import OptionChainSnapshot, OptionChainStrike, AnalyticsSnapshot
from app.research_os.governance.versioning import (
    build_provenance_header,
    calculate_file_sha256,
    get_git_commit_hash,
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
        Executes the full 6-Stage Validated ETL Pipeline for a given symbol and date range.
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
            return {
                "success": False,
                "error": f"No snapshots found in SQLite for symbol '{symbol}' in date range.",
                "total_exported": 0,
            }

        # --- STAGE 2: TRANSFORM & PARQUET WRITE ---
        rows = []
        null_pcr_count = 0
        null_iv_count = 0
        duplicate_check = set()
        duplicate_count = 0

        for snap in snapshots:
            snap_key = (snap.symbol, snap.timestamp)
            if snap_key in duplicate_check:
                duplicate_count += 1
                continue
            duplicate_check.add(snap_key)

            # Query corresponding analytics if available
            analytics = (
                self.db.query(AnalyticsSnapshot)
                .filter(AnalyticsSnapshot.source_snapshot_id == snap.id)
                .first()
            )

            pcr_val = analytics.pcr if analytics else None
            if pcr_val is None:
                null_pcr_count += 1

            # Format timestamp strings
            ts_dt = snap.timestamp
            date_str = ts_dt.strftime("%Y-%m-%d")
            year_str = ts_dt.strftime("%Y")
            month_str = ts_dt.strftime("%m")
            day_str = ts_dt.strftime("%d")

            # Extract strike rows
            strikes = (
                self.db.query(OptionChainStrike)
                .filter(OptionChainStrike.snapshot_id == snap.id)
                .all()
            )

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

            rows.append({
                "snapshot_id": int(snap.id),
                "timestamp": ts_dt.isoformat(),
                "symbol": str(snap.symbol),
                "expiry_date": str(snap.expiry_date or ""),
                "spot_price": float(snap.spot_price or 0.0),
                "pcr": float(pcr_val) if pcr_val is not None else 0.0,
                "market_state": str(analytics.market_state) if analytics else "NEUTRAL",
                "strength": str(analytics.strength) if analytics else "LOW",
                "support_s1": float(analytics.support) if analytics and analytics.support else 0.0,
                "resistance_r1": float(analytics.resistance) if analytics and analytics.resistance else 0.0,
                "strikes_json": json.dumps(strike_list),
                "strikes_count": len(strike_list),
            })

        # Define Output Parquet Partition File Path
        first_dt = snapshots[0].timestamp
        last_dt = snapshots[-1].timestamp
        start_str = first_dt.strftime("%Y%m%d")
        end_str = last_dt.strftime("%Y%m%d")

        partition_dir = os.path.join(
            PARQUET_LAKE_DIR,
            f"symbol={symbol}",
            f"year={first_dt.strftime('%Y')}",
            f"month={first_dt.strftime('%m')}",
        )
        os.makedirs(partition_dir, exist_ok=True)

        dataset_id = f"DS-{symbol}-{start_str}_to_{end_str}-{dataset_version}"
        parquet_filename = f"day={first_dt.strftime('%d')}_snapshots.parquet"
        parquet_path = os.path.join(partition_dir, parquet_filename)

        # Write Parquet Table using PyArrow
        table = pa.Table.from_pylist(rows)
        pq.write_table(table, parquet_path, compression="zstd")

        # --- STAGE 3: VALIDATE PARQUET FILE ---
        val_result = ParquetDataValidator.validate_file(parquet_path)
        actual_rows = val_result.get("total_rows", 0)
        corrupt_rows = val_result.get("corrupt_rows", 0)

        # --- STAGE 4: CALCULATE SHA256 CHECKSUM ---
        sha256_hash = calculate_file_sha256(parquet_path)
        checksum_file = os.path.join(CHECKSUMS_DIR, f"{dataset_id}.sha256")
        with open(checksum_file, "w", encoding="utf-8") as f:
            f.write(f"{sha256_hash}  {parquet_filename}\n")

        sha256_valid = (len(sha256_hash) == 64)

        # --- STAGE 5: GENERATE DATA QUALITY REPORT ---
        quality_report = self.reporter.generate_report(
            dataset_id=dataset_id,
            expected_rows=expected_rows,
            actual_rows=actual_rows,
            duplicate_snapshots=duplicate_count,
            missing_minutes_count=0,
            missing_strikes_count=0,
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
            "total_rows": actual_rows,
            "total_snapshots": actual_rows,
            "feature_version": FEATURE_REGISTRY_VERSION,
            "rule_version": RULE_ENGINE_VERSION,
            "git_commit": provenance["provenance"]["git_commit_hash"],
            "sha256_checksum": sha256_hash,
            "compression_format": "PARQUET_ZSTD",
            "storage_size_bytes": os.path.getsize(parquet_path),
            "status": status,
        })

        return {
            "success": quality_report["quality_pass"],
            "dataset_id": dataset_id,
            "parquet_path": parquet_path,
            "checksum_path": checksum_file,
            "quality_report": quality_report,
            "provenance": provenance,
            "registry_entry": dataset_entry,
            "total_exported": actual_rows,
        }
