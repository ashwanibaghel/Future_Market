"""
Sprint AC — Secondary Memory Index Builder
Builds high-speed secondary memory lookup index (`memory_secondary_index.json`)
mapping situation_id, symbol, trend, and structure directly to partition file paths.
Enables Stage 1 Fast Candidate Filtering across 66,000+ historical memories.
"""

import os
import sys
import glob
import json
import logging
from typing import Dict, Any, List

import pyarrow.parquet as pq

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

MEM_STORE_DIR = "E:/Future Stock/research_storage/memory_store/exchange=NSE_FO"
INDEX_FILE    = "E:/Future Stock/research_storage/memory_store/memory_secondary_index.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("sprint_ac_index")

def build_secondary_memory_index() -> Dict[str, Any]:
    log.info("=" * 60)
    log.info("BUILDING SPRINT AC SECONDARY MEMORY LOOKUP INDEX")
    log.info("=" * 60)

    mem_files = glob.glob(MEM_STORE_DIR + "/**/episodic_memories.parquet", recursive=True)
    log.info("Indexing %d Memory Store Parquet partitions...", len(mem_files))

    index_data = {
        "by_symbol": {},
        "by_situation": {},
        "by_structure": {},
        "by_month": {},
        "total_indexed_memories": 0,
        "total_partitions": len(mem_files)
    }

    total_mems = 0

    for mf in sorted(mem_files):
        rel_path = mf.replace("E:/Future Stock/", "").replace("\\", "/")
        try:
            tbl = pq.ParquetFile(mf).read()
            dict_data = tbl.to_pydict()
            num_rows = tbl.num_rows

            for i in range(num_rows):
                total_mems += 1
                mid = dict_data["memory_id"][i]
                sym = dict_data["symbol"][i]
                sit = dict_data["primary_situation"][i]
                start_t = dict_data["start_time"][i]
                feats = json.loads(dict_data["features_json"][i])
                struct = feats.get("structure", "RANGE_COMPRESSION")

                ym = start_t[:7] if len(start_t) >= 7 else "UNKNOWN"

                # 1. Index by Symbol
                if sym not in index_data["by_symbol"]:
                    index_data["by_symbol"][sym] = []
                index_data["by_symbol"][sym].append(mid)

                # 2. Index by Situation
                if sit not in index_data["by_situation"]:
                    index_data["by_situation"][sit] = []
                index_data["by_situation"][sit].append({"memory_id": mid, "partition": rel_path})

                # 3. Index by Structure
                if struct not in index_data["by_structure"]:
                    index_data["by_structure"][struct] = []
                index_data["by_structure"][struct].append(mid)

                # 4. Index by Month
                if ym not in index_data["by_month"]:
                    index_data["by_month"][ym] = []
                index_data["by_month"][ym].append(mid)

        except Exception as e:
            log.error("Error indexing partition %s: %s", mf, e)

    index_data["total_indexed_memories"] = total_mems

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2)

    log.info("=" * 60)
    log.info("SECONDARY MEMORY INDEX BUILD COMPLETE!")
    log.info("Total Indexed Memories: %d", total_mems)
    log.info("Index File Saved     : %s", INDEX_FILE)
    log.info("=" * 60)

    return index_data

if __name__ == "__main__":
    build_secondary_memory_index()
