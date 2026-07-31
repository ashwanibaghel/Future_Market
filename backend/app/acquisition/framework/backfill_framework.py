import os
import logging
from typing import Dict, Any, List, Optional
import pyarrow as pa
import pyarrow.parquet as pq

from app.acquisition.framework.base_collector import BaseCollectorPlugin
from app.acquisition.framework.provenance import DataProvenance
from app.acquisition.framework.dataset_manifest import DatasetManifest
from app.acquisition.framework.storage_registry import StorageRegistry
from app.research_os.governance.dataset_registry import DatasetRegistry

logger = logging.getLogger("acquisition.framework.backfill")


class HistoricalBackfillFramework:
    """
    Generic Resumable Historical Backfill Engine.
    Executes BaseCollectorPlugin instances, builds DataProvenance, registers DatasetManifest,
    and persists canonical Parquet partitions into StorageRegistry.
    """

    def __init__(
        self,
        collector: BaseCollectorPlugin,
        storage_registry: Optional[StorageRegistry] = None,
        dataset_registry: Optional[DatasetRegistry] = None,
    ):
        self.collector = collector
        self.storage = storage_registry or StorageRegistry()
        self.dataset_registry = dataset_registry or DatasetRegistry()

    def run_backfill_chunk(
        self,
        exchange: str,
        symbol: str,
        year: str,
        month: str,
        start_date: str,
        end_date: str,
    ) -> Optional[DatasetManifest]:
        """
        Runs backfill for a specific symbol date chunk.
        Generates DataProvenance and registers DatasetManifest.
        """
        table = self.collector.fetch_historical_chunk(symbol, start_date, end_date)
        if table is None or table.num_rows == 0:
            logger.warning("No data collected for %s (%s to %s)", symbol, start_date, end_date)
            return None

        # Build Storage Partition Path
        path = self.storage.get_canonical_partition_path(exchange, symbol, year, month, self.collector.asset_type)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        # Persist ZSTD Parquet Table
        pq.write_table(table, path, compression="zstd")
        file_size = os.path.getsize(path)

        with open(path, "rb") as f:
            content_bytes = f.read()

        # Generate DataProvenance
        prov = DataProvenance.create(
            provider=self.collector.source_name,
            content_bytes=content_bytes,
            latency_ms=45.0,
        )

        dataset_id = f"CANONICAL-{self.collector.asset_type}-{symbol.upper()}-{year}-{int(month):02d}"

        # Requirement 1: Construct DatasetManifest
        manifest = DatasetManifest(
            dataset_id=dataset_id,
            dataset_version="D-v1.0.0",
            schema_version="CS-v1.0.0",
            provider=self.collector.source_name,
            symbols=[symbol.upper()],
            asset_type=self.collector.asset_type,
            time_range={"start_date": start_date, "end_date": end_date},
            row_count=table.num_rows,
            checksum=prov.sha256_checksum,
        )

        # Register in DatasetRegistry
        self.dataset_registry.register_dataset({
            "dataset_id": dataset_id,
            "dataset_version": manifest.dataset_version,
            "schema_version": manifest.schema_version,
            "dataset_type": f"CANONICAL_{self.collector.asset_type}",
            "symbol": symbol.upper(),
            "year": str(year),
            "month": f"{int(month):02d}",
            "total_rows": table.num_rows,
            "storage_size_bytes": file_size,
            "sha256_checksum": prov.sha256_checksum,
            "status": "RESEARCH_READY",
        })

        logger.info("Backfill framework completed chunk '%s' (%d rows, %d KB)", dataset_id, table.num_rows, file_size // 1024)
        return manifest
