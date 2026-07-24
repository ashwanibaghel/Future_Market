import os
import logging
from typing import Dict, Any
import pyarrow.parquet as pq

logger = logging.getLogger("research_os.datalake.validator")


class ParquetDataValidator:
    """Stage 3 Validator in the 6-Stage Validated ETL Pipeline."""

    @staticmethod
    def validate_file(filepath: str) -> Dict[str, Any]:
        """
        Rigorously validates a Parquet file for structural integrity across ALL 
        row groups, ensuring zero data corruption and full readability.
        """
        if not os.path.exists(filepath):
            logger.error("Validation failed: File does not exist (%s)", filepath)
            return {
                "valid": False,
                "error": f"File does not exist: {filepath}",
                "total_rows": 0,
                "corrupt_rows": 0,
            }

        file_size = os.path.getsize(filepath)
        if file_size == 0:
            logger.error("Validation failed: File size is 0 bytes (%s)", filepath)
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
            schema = parquet_file.schema

            if total_rows == 0:
                logger.error("Validation failed: Parquet file contains 0 rows (%s)", filepath)
                return {
                    "valid": False,
                    "error": "Parquet file contains 0 rows",
                    "total_rows": 0,
                    "corrupt_rows": 0,
                }

            # --- CRITICAL FIX: SCAN ALL ROW GROUPS FOR ZERO CORRUPTION ---
            corrupt_row_groups = 0
            scanned_rows = 0

            for rg_idx in range(num_row_groups):
                try:
                    rg_table = parquet_file.read_row_group(rg_idx)
                    if rg_table is None or rg_table.num_rows == 0:
                        corrupt_row_groups += 1
                    else:
                        scanned_rows += rg_table.num_rows
                except Exception as rg_exc:
                    logger.error("Corrupt row group %d in %s: %s", rg_idx, filepath, str(rg_exc))
                    corrupt_row_groups += 1

            if corrupt_row_groups > 0 or scanned_rows != total_rows:
                logger.error("Parquet validation failed: %d corrupt row group(s) in %s", corrupt_row_groups, filepath)
                return {
                    "valid": False,
                    "error": f"Failed reading {corrupt_row_groups} row group(s) out of {num_row_groups}",
                    "total_rows": total_rows,
                    "corrupt_rows": total_rows - scanned_rows if scanned_rows < total_rows else corrupt_row_groups,
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
            logger.error("Fatal Parquet corruption error for %s: %s", filepath, str(exc))
            return {
                "valid": False,
                "error": f"Parquet corruption error: {str(exc)}",
                "total_rows": 0,
                "corrupt_rows": -1,
            }

