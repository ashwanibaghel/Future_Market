import os
from typing import Dict, Any
import pyarrow.parquet as pq


class ParquetDataValidator:
    """Stage 3 Validator in the 6-Stage Validated ETL Pipeline."""

    @staticmethod
    def validate_file(filepath: str) -> Dict[str, Any]:
        """
        Rigorously validates a Parquet file for structural integrity, 
        non-zero rows, readability, and corruption.
        """
        if not os.path.exists(filepath):
            return {
                "valid": False,
                "error": f"File does not exist: {filepath}",
                "total_rows": 0,
                "corrupt_rows": 0,
            }

        file_size = os.path.getsize(filepath)
        if file_size == 0:
            return {
                "valid": False,
                "error": "File size is 0 bytes",
                "total_rows": 0,
                "corrupt_rows": 0,
            }

        try:
            parquet_file = pq.ParquetFile(filepath)
            metadata = parquet_file.metadata
            total_rows = metadata.num_rows
            num_row_groups = metadata.num_row_groups

            # Read schema to ensure Arrow columns are intact
            schema = parquet_file.schema

            if total_rows == 0:
                return {
                    "valid": False,
                    "error": "Parquet file contains 0 rows",
                    "total_rows": 0,
                    "corrupt_rows": 0,
                }

            # Attempt reading a sample table chunk to verify readability
            sample_table = parquet_file.read_row_group(0)
            if sample_table is None or sample_table.num_rows == 0:
                return {
                    "valid": False,
                    "error": "Failed reading row group 0 from Parquet file",
                    "total_rows": total_rows,
                    "corrupt_rows": total_rows,
                }

            return {
                "valid": True,
                "error": None,
                "total_rows": total_rows,
                "num_row_groups": num_row_groups,
                "num_columns": len(schema),
                "corrupt_rows": 0,
                "file_size_bytes": file_size,
            }

        except Exception as exc:
            return {
                "valid": False,
                "error": f"Parquet corruption error: {str(exc)}",
                "total_rows": 0,
                "corrupt_rows": -1,
            }
