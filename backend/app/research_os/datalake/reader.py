import os
import glob
import logging
from typing import Dict, Any, List, Optional
import pyarrow.dataset as ds
import pyarrow.parquet as pq

logger = logging.getLogger("research_os.datalake.reader")

try:
    import duckdb
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False
    logger.warning("DuckDB package not installed; falling back to PyArrow Dataset scanner.")

from app.research_os.governance.dataset_registry import PARQUET_LAKE_DIR


class DuckDBDataReader:
    """
    High-speed analytical reader for historical Parquet Lake partitions.
    Uses DuckDB SIMD vectorization when available, with PyArrow Dataset fallbacks.
    """

    def __init__(self, data_lake_dir: str = PARQUET_LAKE_DIR):
        self.lake_dir = data_lake_dir
        if HAS_DUCKDB:
            self.conn = duckdb.connect(database=":memory:")
        else:
            self.conn = None

    def query_snapshots(
        self,
        symbol: str,
        year: Optional[str] = None,
        month: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Queries historical snapshots from the Parquet Lake partitions safely.
        """
        # Sanitize symbol parameter
        safe_symbol = "".join(c for c in symbol if c.isalnum() or c in ("_", "-"))
        search_pattern = os.path.join(self.lake_dir, f"symbol={safe_symbol}")

        if year:
            safe_year = "".join(c for c in year if c.isdigit())
            search_pattern = os.path.join(search_pattern, f"year={safe_year}")
        else:
            search_pattern = os.path.join(search_pattern, "year=*")
        
        if month:
            safe_month = "".join(c for c in month if c.isdigit())
            search_pattern = os.path.join(search_pattern, f"month={safe_month}")
        else:
            search_pattern = os.path.join(search_pattern, "month=*")
        
        search_pattern = os.path.join(search_pattern, "*.parquet")
        parquet_files = glob.glob(search_pattern)

        if not parquet_files:
            logger.info("No Parquet partitions found matching pattern: %s", search_pattern)
            return []

        if HAS_DUCKDB and self.conn:
            pattern_glob = search_pattern.replace("\\", "/")
            sql = """
                SELECT snapshot_id, timestamp, symbol, expiry_date, spot_price, pcr, market_state, strength, strikes_count 
                FROM read_parquet(?)
                ORDER BY timestamp ASC
                LIMIT ?
            """
            res = self.conn.execute(sql, [pattern_glob, limit]).fetchall()
            cols = ["snapshot_id", "timestamp", "symbol", "expiry_date", "spot_price", "pcr", "market_state", "strength", "strikes_count"]
            return [dict(zip(cols, row)) for row in res]
        else:
            # PyArrow Dataset Scanner (Streaming projection fallback)
            logger.debug("Executing query via PyArrow dataset scanner")
            dataset = ds.dataset(parquet_files, format="parquet")
            scanner = dataset.scanner(
                columns=["snapshot_id", "timestamp", "symbol", "expiry_date", "spot_price", "pcr", "market_state", "strength", "strikes_count"],
            )
            table = scanner.head(limit)
            return table.to_pylist()

    def get_lake_summary(self) -> Dict[str, Any]:
        """Returns statistics on the Parquet Data Lake partitions."""
        pattern = os.path.join(self.lake_dir, "**", "*.parquet")
        files = glob.glob(pattern, recursive=True)
        
        total_bytes = sum(os.path.getsize(f) for f in files) if files else 0
        total_files = len(files)

        return {
            "lake_directory": self.lake_dir,
            "has_duckdb_accelerator": HAS_DUCKDB,
            "total_parquet_files": total_files,
            "total_size_bytes": total_bytes,
            "total_size_mb": round(total_bytes / (1024 * 1024), 2),
        }

