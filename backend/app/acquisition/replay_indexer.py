import os
import glob
import json
import logging
from typing import Dict, Any, List
import pyarrow as pa
import pyarrow.parquet as pq

from app.research_os.governance.dataset_registry import (
    RESEARCH_STORAGE_DIR,
    PARQUET_LAKE_DIR,
    ensure_research_storage_structure,
)

logger = logging.getLogger("acquisition.replay_indexer")

REPLAY_INDEX_DIR = os.path.join(RESEARCH_STORAGE_DIR, "replay_index")

REPLAY_INDEX_SCHEMA = pa.schema([
    ("index_id", pa.string()),
    ("symbol", pa.string()),
    ("year", pa.string()),
    ("month", pa.string()),
    ("partition_file", pa.string()),
    ("start_timestamp", pa.string()),
    ("end_timestamp", pa.string()),
    ("total_rows", pa.int64()),
    ("file_size_bytes", pa.int64()),
    ("sha256_checksum", pa.string()),
    ("status", pa.string()),
])


class ReplayIndexBuilder:
    """
    Phase 6: Replay Ready Index Builder.
    Creates ultra-fast index lookup tables allowing the future Replay Engine to query
    specific dates, weeks, months, or strikes without scanning the full Data Lake.
    """

    def __init__(self, data_lake_dir: str = PARQUET_LAKE_DIR):
        self.lake_dir = data_lake_dir
        os.makedirs(REPLAY_INDEX_DIR, exist_ok=True)
        self.index_parquet = os.path.join(REPLAY_INDEX_DIR, "replay_index.parquet")
        self.index_json = os.path.join(REPLAY_INDEX_DIR, "replay_index.json")


    def build_index_for_lake(self) -> Dict[str, Any]:
        """
        Scans all Parquet Lake partitions and constructs the Replay Ready Index.
        """
        pattern = os.path.join(self.lake_dir, "**", "*.parquet")
        files = glob.glob(pattern, recursive=True)

        entries: List[Dict[str, Any]] = []
        total_rows_indexed = 0

        for pfile in files:
            try:
                pf = pq.ParquetFile(pfile)
                meta = pf.metadata
                num_rows = meta.num_rows

                # Extract partition hierarchy from path
                norm_path = pfile.replace("\\", "/")
                parts = norm_path.split("/")
                symbol = "NIFTY"
                year = "2026"
                month = "07"

                for part in parts:
                    if part.startswith("symbol="):
                        symbol = part.split("=")[1].replace("_OPTIONS", "")
                    elif part.startswith("year="):
                        year = part.split("=")[1]
                    elif part.startswith("month="):
                        month = part.split("=")[1]

                # Read first and last timestamp if rows > 0
                start_ts, end_ts = "", ""
                if num_rows > 0:
                    table_sample = pf.read_row_group(0, columns=["timestamp"])
                    start_ts = str(table_sample.column("timestamp")[0])
                    end_ts = str(table_sample.column("timestamp")[-1])

                idx_id = f"IDX-{symbol}-{year}-{month}"
                file_size = os.path.getsize(pfile)

                entry = {
                    "index_id": idx_id,
                    "symbol": symbol,
                    "year": year,
                    "month": month,
                    "partition_file": pfile,
                    "start_timestamp": start_ts,
                    "end_timestamp": end_ts,
                    "total_rows": num_rows,
                    "file_size_bytes": file_size,
                    "sha256_checksum": "",
                    "status": "READY",
                }
                entries.append(entry)
                total_rows_indexed += num_rows

            except Exception as exc:
                logger.warning("Failed indexing file %s: %s", pfile, str(exc))

        # Persist Replay Index JSON & Parquet
        with open(self.index_json, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)

        if entries:
            table = pa.Table.from_pylist(entries, schema=REPLAY_INDEX_SCHEMA)
            pq.write_table(table, self.index_parquet, compression="zstd")

        return {
            "total_partitions_indexed": len(entries),
            "total_rows_indexed": total_rows_indexed,
            "index_parquet": self.index_parquet,
            "index_json": self.index_json,
        }
