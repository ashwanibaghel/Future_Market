"""
Sprint AA — Market Situation Understanding Engine v1
Situation Replay Inspector / Console Visualizer.

Terminal visualizer tool allowing quantitative research engineers to step through replay
snapshots and inspect evolving AI market situations, temporal evolution phases,
4-pillar market context, reasoning strings, and explicit unknowns.
"""

import sys
import os
import glob
import json
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import pyarrow.parquet as pq

SIT_STORE_DIR = "E:/Future Stock/research_storage/situation_store/exchange=NSE_FO"

def visualize_situation_stream(symbol: str = "NIFTY", limit: int = 5, sample: bool = True):
    print("=" * 75)
    print(f"  MARKET SITUATION UNDERSTANDING ENGINE v1 -- REPLAY INSPECTOR ({symbol})")
    print("=" * 75)

    sit_files = glob.glob(SIT_STORE_DIR + f"/symbol={symbol}/**/situations.parquet", recursive=True)
    if not sit_files:
        print(f"No situation store files found for symbol {symbol} at {SIT_STORE_DIR}")
        return

    sample_file = sit_files[-1] if sample else sit_files[0]
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
                "situations": []
            }
        
        snaps_map[ts]["situations"].append({
            "situation_id": dict_data["situation_id"][i],
            "evolution_phase": dict_data["evolution_phase"][i],
            "confidence": dict_data["confidence"][i],
            "severity": dict_data["severity"][i],
            "duration_minutes": dict_data["duration_minutes"][i],
            "why": json.loads(dict_data["why_json"][i]),
            "reasoning": dict_data["reasoning"][i],
            "unknowns": json.loads(dict_data["unknowns_json"][i]),
            "supporting_observations": json.loads(dict_data["supporting_observations_json"][i]),
            "market_context": json.loads(dict_data["market_context_json"][i]),
            "evidence": json.loads(dict_data["evidence_json"][i])
        })

    sorted_timestamps = sorted(snaps_map.keys())
    print(f"Loaded {len(sorted_timestamps)} unique snapshot timestamps from situation partition.")
    print("-" * 75)

    count = 0
    for ts in sorted_timestamps:
        count += 1
        if count > limit:
            break

        snap = snaps_map[ts]
        print(f"\n[TIME] Timestamp  : {snap['timestamp']} | Symbol: {symbol}")
        print(f"[MARKET] Spot Price = {snap['spot_price']:.2f} | ATM Strike = {snap['atm_strike']:.1f}")
        print("[AI UNDERSTANDING] Evolving Market Situations:")

        for sit in snap["situations"]:
            phase_badge = f"[{sit['evolution_phase']} - Duration: {sit['duration_minutes']}m]"
            conf_badge = f"(Conf: {sit['confidence']*100:.1f}%)"
            ctx = sit['market_context']
            
            print(f"   |-- {sit['situation_id']} {phase_badge} {conf_badge}")
            print(f"   |   4-Pillar Context: Trend={ctx['trend']} | Volatility={ctx['volatility']} | Flow={ctx['participation']} | Structure={ctx['structure']}")
            print(f"   |   Cognitive Reasoning: {sit['reasoning']}")
            print(f"   |   Explicit Unknowns : {', '.join(sit['unknowns']) if sit['unknowns'] else 'None'}")
            print(f"   |   Supporting Obs    : {', '.join(sit['supporting_observations'])}")

        print("   " + "-" * 65)

    print("\n" + "=" * 75)
    print("  VISUALIZATION COMPLETE -- 100% EXPLAINABLE SITUATION TIMELINE")
    print("=" * 75)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sprint AA Situation Engine Visualizer")
    parser.add_argument("--symbol", type=str, default="NIFTY", help="Symbol to inspect (NIFTY or BANKNIFTY)")
    parser.add_argument("--limit", type=int, default=5, help="Number of snapshots to display")
    parser.add_argument("--sample", action="store_true", help="Sample latest partition")

    args = parser.parse_args()
    visualize_situation_stream(symbol=args.symbol, limit=args.limit, sample=True)
