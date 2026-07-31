"""
Sprint Z — Artificial Market Perception Engine v1
Observation Replay Visualizer / Console Inspector.

Terminal visualizer tool allowing quantitative research engineers to step through replay
snapshots and inspect live AI market observations and explainable evidence cards.
"""

import sys
import os
import glob
import json
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import pyarrow.parquet as pq

OBS_STORE_DIR = "E:/Future Stock/research_storage/observation_store/exchange=NSE_FO"

def visualize_replay_stream(symbol: str = "NIFTY", limit: int = 5, sample: bool = True):
    print("=" * 70)
    print(f"  ARTIFICIAL MARKET PERCEPTION ENGINE v1 -- REPLAY INSPECTOR ({symbol})")
    print("=" * 70)

    obs_files = glob.glob(OBS_STORE_DIR + f"/symbol={symbol}/**/observations.parquet", recursive=True)
    if not obs_files:
        print(f"No observation store files found for symbol {symbol} at {OBS_STORE_DIR}")
        return

    sample_file = obs_files[-1] if sample else obs_files[0]
    print(f"Reading Partition File: {sample_file}\n")

    pfile = pq.ParquetFile(sample_file)
    tbl = pfile.read()
    dict_data = tbl.to_pydict()
    num_rows = tbl.num_rows

    snaps_map = {}
    for i in range(num_rows):
        ts = dict_data["timestamp"][i]
        if ts not in snaps_map:
            snaps_map[ts] = {
                "snapshot_id": dict_data["snapshot_id"][i],
                "timestamp": ts,
                "spot_price": dict_data["spot_price"][i],
                "atm_strike": dict_data["atm_strike"][i],
                "observations": []
            }
        
        snaps_map[ts]["observations"].append({
            "observation_id": dict_data["observation_id"][i],
            "category": dict_data["category"][i],
            "confidence": dict_data["confidence"][i],
            "severity": dict_data["severity"][i],
            "severity_level": dict_data["severity_level"][i],
            "description": dict_data["description"][i],
            "evidence": json.loads(dict_data["evidence_json"][i])
        })

    sorted_timestamps = sorted(snaps_map.keys())
    print(f"Loaded {len(sorted_timestamps)} unique snapshot timestamps from partition.")
    print("-" * 70)

    count = 0
    for ts in sorted_timestamps:
        count += 1
        if count > limit:
            break

        snap = snaps_map[ts]
        print(f"\n[TIME] Timestamp  : {snap['timestamp']} | Symbol: {symbol}")
        print(f"[MARKET] Spot Price = {snap['spot_price']:.2f} | ATM Strike = {snap['atm_strike']:.1f}")
        print("[AI PERCEPTION] Observations:")

        for obs in snap["observations"]:
            sev_badge = f"[{obs['severity']} - Level {obs['severity_level']}]"
            conf_badge = f"(Conf: {obs['confidence']*100:.1f}%)"
            print(f"   |-- {obs['observation_id']} {sev_badge} {conf_badge}")
            print(f"   |   Description: {obs['description']}")
            print(f"   |   Evidence   : {json.dumps(obs['evidence'])}")

        print("   " + "-" * 60)

    print("\n" + "=" * 70)
    print("  VISUALIZATION COMPLETE -- 100% EXPLAINABLE PERCEPTION STREAM")
    print("=" * 70)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sprint Z Perception Engine Visualizer")
    parser.add_argument("--symbol", type=str, default="NIFTY", help="Symbol to inspect (NIFTY or BANKNIFTY)")
    parser.add_argument("--limit", type=int, default=5, help="Number of snapshots to display")
    parser.add_argument("--sample", action="store_true", help="Sample latest partition")

    args = parser.parse_args()
    visualize_replay_stream(symbol=args.symbol, limit=args.limit, sample=True)
