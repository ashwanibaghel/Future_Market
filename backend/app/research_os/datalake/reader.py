import os
import glob
from typing import Dict, Any, List, Optional
import pyarrow.dataset as ds
import pyarrow.parquet as pq

try:
    import duckdb
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False

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
        Queries historical snapshots from the Parquet Lake partitions.
        """
        search_pattern = os.path.join(self.lake_dir, f"symbol={symbol}")
        if year:
            search_pattern = os.path.join(search_pattern, f"year={year}")
        else:
            search_pattern = os.path.join(search_pattern, "year=*")
        
        if month:
            search_pattern = os.path.join(search_pattern, f"month={month}")
        else:
            search_pattern = os.path.join(search_pattern, "month=*")
        
        search_pattern = os.path.join(search_pattern, "*.parquet")

        parquet_files = glob.glob(search_pattern)
        if not parquet_files:
            return []

        if HAS_DUCKDB and self.conn:
            # DuckDB SQL vector scan query
            pattern_glob = search_pattern.replace("\\", "/")
            sql = f"""
                SELECT snapshot_id, timestamp, symbol, expiry_date, spot_price, pcr, market_state, strength, strikes_count 
                FROM read_parquet('{pattern_glob}')
                ORDER BY timestamp ASC
                LIMIT {limit}
            """
            res = self.conn.execute(sql).fetchall()
            cols = ["snapshot_id", "timestamp", "symbol", "expiry_date", "spot_price", "pcr", "market_state", "strength", "strikes_count"]
            return [dict(zip(cols, row)) for row in res]
        else:
            # PyArrow Dataset Fallback
            dataset = ds.dataset(parquet_files, format="parquet")
            table = dataset.to_table()
            if limit and limit < table.num_rows:
                table = table.slice(0, limit)
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
