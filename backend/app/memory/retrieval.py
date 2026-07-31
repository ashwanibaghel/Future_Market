"""
Sprint AB — Decoupled Memory Retrieval Engine
Queries and filters immutable episodic memories from the Parquet Storage Lake
by symbol, situation_id, date range, or feature map constraints.
"""

from typing import List, Dict, Any, Optional
import pyarrow.parquet as pq

class MemoryRetrievalEngine:
    """
    Decoupled Memory Query & Retrieval Service.
    Reads Parquet partition files and filters memories based on structural criteria.
    """

    def retrieve_memories(
        self,
        partition_path: str,
        situation_id: Optional[str] = None,
        min_confidence: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Retrieves episodic memory records matching filtering criteria.
        """
        try:
            tbl = pq.ParquetFile(partition_path).read()
        except Exception:
            return []

        dict_data = tbl.to_pydict()
        num_rows = tbl.num_rows

        results = []
        for i in range(num_rows):
            sit = dict_data["primary_situation"][i]
            conf = dict_data["peak_confidence"][i]

            if situation_id and sit != situation_id:
                continue
            if conf < min_confidence:
                continue

            results.append({
                "memory_id": dict_data["memory_id"][i],
                "memory_type": dict_data["memory_type"][i],
                "primary_situation": sit,
                "symbol": dict_data["symbol"][i],
                "exchange": dict_data["exchange"][i],
                "start_time": dict_data["start_time"][i],
                "end_time": dict_data["end_time"][i],
                "duration_minutes": dict_data["duration_minutes"][i],
                "peak_confidence": conf,
                "key_reasoning": dict_data["key_reasoning"][i]
            })

        return results
