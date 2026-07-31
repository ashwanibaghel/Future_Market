"""
Sprint Y — Phase 1: Dataset Audit
Reads every raw .json.gz file and produces exact factual statistics.
"""
import gzip
import json
import os
import glob
import re
from collections import defaultdict
from datetime import datetime, timezone
import json as json_mod

RAW_BASE = "E:/Future Stock/research_storage/raw/dhan"
REPORT_DIR = "E:/Future Stock/research_storage/quality_reports"
os.makedirs(REPORT_DIR, exist_ok=True)

FILENAME_RE = re.compile(
    r"^(NIFTY|BANKNIFTY)_ATM([+\-]\d+)_(CALL|PUT)_(\d{4}-\d{2}-\d{2})\.json\.gz$"
)

print("=" * 60)
print("  SPRINT Y — PHASE 1: DATASET AUDIT")
print("=" * 60)

all_files = glob.glob(RAW_BASE + "/**/*.json.gz", recursive=True)
print(f"Total raw files found: {len(all_files)}")

# Counters
total_candles = 0
total_size_bytes = 0
symbols = set()
expiries = set()
trading_days = set()
yearly_stats = defaultdict(lambda: {"files": 0, "candles": 0, "expiries": set(), "symbols": set()})
earliest_ts = None
latest_ts = None
empty_files = []
corrupt_files = []
parsed_files = 0

for i, fpath in enumerate(all_files):
    if i % 500 == 0:
        print(f"  Processing {i}/{len(all_files)}...")

    fname = os.path.basename(fpath)
    fsize = os.path.getsize(fpath)
    total_size_bytes += fsize

    m = FILENAME_RE.match(fname)
    if not m:
        corrupt_files.append(fname)
        continue

    symbol, atm_offset, option_type, expiry_date = m.groups()
    year = expiry_date[:4]
    month = expiry_date[5:7]

    symbols.add(symbol)
    expiries.add(f"{symbol}_{expiry_date}")
    yearly_stats[year]["files"] += 1
    yearly_stats[year]["expiries"].add(expiry_date)
    yearly_stats[year]["symbols"].add(symbol)

    try:
        with gzip.open(fpath, "rt", encoding="utf-8") as f:
            data = json.load(f)

        ce_data = data.get("data", {})
        if ce_data is None:
            ce_data = {}
        ce = ce_data.get("ce", {})
        if ce is None:
            ce = {}

        timestamps = ce.get("timestamp", [])
        volumes = ce.get("volume", [])

        n_candles = len(timestamps)
        yearly_stats[year]["candles"] += n_candles
        total_candles += n_candles
        parsed_files += 1

        if n_candles == 0:
            empty_files.append(fname)
        else:
            for ts in timestamps:
                dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                day_str = dt.strftime("%Y-%m-%d")
                trading_days.add(day_str)

            min_ts = min(timestamps)
            max_ts = max(timestamps)
            if earliest_ts is None or min_ts < earliest_ts:
                earliest_ts = min_ts
            if latest_ts is None or max_ts > latest_ts:
                latest_ts = max_ts

    except Exception as e:
        corrupt_files.append(f"{fname}: {e}")

# Convert sets to counts for JSON serialization
report = {
    "phase": "Phase 1 - Dataset Audit",
    "total_raw_files": len(all_files),
    "parsed_files": parsed_files,
    "total_symbols": sorted(list(symbols)),
    "total_expiries": len(expiries),
    "total_trading_days": len(trading_days),
    "earliest_date": datetime.fromtimestamp(earliest_ts, tz=timezone.utc).strftime("%Y-%m-%d") if earliest_ts else None,
    "latest_date": datetime.fromtimestamp(latest_ts, tz=timezone.utc).strftime("%Y-%m-%d") if latest_ts else None,
    "total_candles": total_candles,
    "total_storage_bytes": total_size_bytes,
    "total_storage_mb": round(total_size_bytes / (1024 * 1024), 2),
    "empty_files": len(empty_files),
    "corrupt_or_unparseable_files": len(corrupt_files),
    "yearly_breakdown": {
        yr: {
            "files": v["files"],
            "candles": v["candles"],
            "unique_expiries": len(v["expiries"]),
            "symbols": sorted(list(v["symbols"]))
        }
        for yr, v in sorted(yearly_stats.items())
    },
    "sample_empty_files": empty_files[:10],
    "sample_corrupt_files": corrupt_files[:10],
}

report_path = os.path.join(REPORT_DIR, "sprint_y_phase1_audit.json")
with open(report_path, "w", encoding="utf-8") as f:
    json_mod.dump(report, f, indent=2)

print()
print("=" * 60)
print("  PHASE 1 AUDIT RESULTS")
print("=" * 60)
print(f"  Total Raw Files     : {report['total_raw_files']}")
print(f"  Symbols             : {report['total_symbols']}")
print(f"  Earliest Date       : {report['earliest_date']}")
print(f"  Latest Date         : {report['latest_date']}")
print(f"  Total Trading Days  : {report['total_trading_days']}")
print(f"  Total Expiries      : {report['total_expiries']}")
print(f"  Total Candles       : {report['total_candles']:,}")
print(f"  Total Storage       : {report['total_storage_mb']} MB")
print(f"  Empty Files         : {report['empty_files']}")
print(f"  Corrupt Files       : {report['corrupt_or_unparseable_files']}")
print()
print("  Year-wise breakdown:")
for yr, v in report["yearly_breakdown"].items():
    print(f"    {yr}: {v['files']} files | {v['candles']:,} candles | {v['unique_expiries']} expiries | {v['symbols']}")
print()
print(f"  Report saved: {report_path}")
print("=" * 60)
