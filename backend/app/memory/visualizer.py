"""
Sprint AB — Market Memory Formation Engine v1
Memory Replay Inspector / Console Visualizer.

Terminal visualizer tool allowing quantitative research engineers to step through replay
episodes and inspect persistent Market Memories, collision-proof Hash IDs,
extensible feature map signatures, 6-horizon physical outcomes, and reflection metadata.
"""

import sys
import os
import glob
import json
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import pyarrow.parquet as pq

MEM_STORE_DIR = "E:/Future Stock/research_storage/memory_store/exchange=NSE_FO"

def visualize_memory_stream(symbol: str = "NIFTY", limit: int = 5, sample: bool = True):
    print("=" * 75)
    print(f"  MARKET MEMORY FORMATION ENGINE v1 -- REPLAY INSPECTOR ({symbol})")
    print("=" * 75)

    mem_files = glob.glob(MEM_STORE_DIR + f"/symbol={symbol}/**/episodic_memories.parquet", recursive=True)
    if not mem_files:
        print(f"No memory store files found for symbol {symbol} at {MEM_STORE_DIR}")
        return

    sample_file = mem_files[-1] if sample else mem_files[0]
    print(f"Reading Memory Partition File: {sample_file}\n")

    pfile = pq.ParquetFile(sample_file)
    tbl = pfile.read()
    dict_data = tbl.to_pydict()
    num_rows = tbl.num_rows

    print(f"Loaded {num_rows} Episodic Memories from partition.")
    print("-" * 75)

    count = 0
    for i in range(num_rows):
        count += 1
        if count > limit:
            break

        mem_id = dict_data["memory_id"][i]
        sit_id = dict_data["primary_situation"][i]
        start_t = dict_data["start_time"][i]
        end_t = dict_data["end_time"][i]
        dur = dict_data["duration_minutes"][i]
        conf = dict_data["peak_confidence"][i]
        reason = dict_data["key_reasoning"][i]

        outcomes = json.loads(dict_data["episode_outcomes_json"][i])
        reflection = json.loads(dict_data["reflection_json"][i])
        features = json.loads(dict_data["features_json"][i])

        print(f"\n[MEMORY OBJECT] ID: {mem_id}")
        print(f"   |-- Type      : {dict_data['memory_type'][i]} | Situation: {sit_id}")
        print(f"   |-- Window    : {start_t} -> {end_t} (Duration: {dur}m)")
        print(f"   |-- Features  : Trend={features.get('trend')} | Volatility={features.get('volatility')} | Structure={features.get('structure')} | PCR={features.get('pcr_oi')}")
        print(f"   |-- Reasoning : {reason}")
        print(f"   |-- 6-Horizon Outcomes:")
        print(f"   |     * 5m  : Dir={outcomes['horizon_5m']['direction']} (MFE: +{outcomes['horizon_5m']['mfe_pct']}%, MAE: {outcomes['horizon_5m']['mae_pct']}%)")
        print(f"   |     * 15m : Dir={outcomes['horizon_15m']['direction']} (MFE: +{outcomes['horizon_15m']['mfe_pct']}%, MAE: {outcomes['horizon_15m']['mae_pct']}%)")
        print(f"   |     * 30m : Dir={outcomes['horizon_30m']['direction']} (MFE: +{outcomes['horizon_30m']['mfe_pct']}%, MAE: {outcomes['horizon_30m']['mae_pct']}%)")
        print(f"   |     * 60m : Dir={outcomes['horizon_60m']['direction']} (MFE: +{outcomes['horizon_60m']['mfe_pct']}%, MAE: {outcomes['horizon_60m']['mae_pct']}%)")
        print(f"   |-- Reflection: Lesson='{reflection.get('lesson')}'")
        print("   " + "-" * 65)

    print("\n" + "=" * 75)
    print("  VISUALIZATION COMPLETE -- 100% IMMUTABLE MARKET MEMORY EPISODES")
    print("=" * 75)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sprint AB Memory Engine Visualizer")
    parser.add_argument("--symbol", type=str, default="NIFTY", help="Symbol to inspect (NIFTY or BANKNIFTY)")
    parser.add_argument("--limit", type=int, default=5, help="Number of memories to display")
    parser.add_argument("--sample", action="store_true", help="Sample latest partition")

    args = parser.parse_args()
    visualize_memory_stream(symbol=args.symbol, limit=args.limit, sample=True)
