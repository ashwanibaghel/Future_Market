import os
import logging
from typing import Dict, Any, Optional
from app.research_os.governance.dataset_registry import RESEARCH_STORAGE_DIR, PARQUET_LAKE_DIR, ensure_research_storage_structure

RAW_ARCHIVE_DIR = os.path.join(RESEARCH_STORAGE_DIR, "raw_archive")

logger = logging.getLogger("acquisition.framework.storage_registry")


class StorageRegistry:
    """Manages Hive Parquet partition paths and dataset storage manifests."""

    def __init__(self, base_lake_dir: str = PARQUET_LAKE_DIR, raw_archive_dir: str = RAW_ARCHIVE_DIR):
        ensure_research_storage_structure()
        self.base_lake_dir = base_lake_dir
        self.raw_archive_dir = raw_archive_dir

    def get_canonical_partition_path(self, exchange: str, symbol: str, year: str, month: str, asset_type: str = "OPTIONS") -> str:
        """Constructs canonical Hive Parquet partition storage path."""
        m_str = f"{int(month):02d}"
        if asset_type == "OPTIONS":
            sym_dir = f"symbol={symbol.upper()}_OPTIONS"
            file_name = "option_chain.parquet"
        elif asset_type == "EQUITIES":
            sym_dir = f"symbol={symbol.upper()}"
            file_name = "candles.parquet"
        else:
            sym_dir = f"symbol={symbol.upper()}"
            file_name = "data.parquet"

        return os.path.join(
            self.base_lake_dir,
            f"exchange={exchange.upper()}",
            sym_dir,
            f"year={year}",
            f"month={m_str}",
            file_name
        )
