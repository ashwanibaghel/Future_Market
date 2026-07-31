import os
import time
import json
import gzip
import tempfile
import pyarrow as pa
from datetime import datetime, timezone
from app.acquisition.normalizer import DataNormalizer, CanonicalOptionCandle, CANONICAL_OPTION_SCHEMA
from app.acquisition.engine import HistoricalBackfillEngine, PROGRESS_FILE


# Synthetic Dhan rolling option response with ~15,000 candle records
def generate_synthetic_dhan_response(num_records: int = 15000) -> dict:
    start_times = [f"2021-01-01T09:{i//60:02d}:{i%60:02d}+05:30" for i in range(num_records)]
    return {
        "status": "success",
        "data": {
            "start_Time": start_times,
            "open": [18000.5 + (i * 0.1) for i in range(num_records)],
            "high": [18010.0 + (i * 0.1) for i in range(num_records)],
            "low": [17990.0 + (i * 0.1) for i in range(num_records)],
            "close": [18005.2 + (i * 0.1) for i in range(num_records)],
            "volume": [100 + i for i in range(num_records)],
            "oi": [50000 + (i * 10) for i in range(num_records)],
            "iv": [15.5 for _ in range(num_records)],
            "spot": [18000.0 for _ in range(num_records)],
        }
    }


def run_phase1_json_gzip_benchmark():
    payload = generate_synthetic_dhan_response(15000)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        file_old = os.path.join(tmpdir, "old.json")
        file_gz = os.path.join(tmpdir, "new.json.gz")

        # Old indented write
        t0 = time.perf_counter()
        with open(file_old, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        t_old = time.perf_counter() - t0

        # New compact gzip write
        t1 = time.perf_counter()
        compact_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        compressed = gzip.compress(compact_bytes)
        with open(file_gz, "wb") as f:
            f.write(compressed)
        t_new = time.perf_counter() - t1

        old_size = os.path.getsize(file_old)
        gz_size = os.path.getsize(file_gz)
        speedup = t_old / max(t_new, 1e-6)
        reduction_pct = ((old_size - gz_size) / old_size) * 100

        print(f"\n[AMENDMENT 3 BENCHMARK - GZIP ARCHIVAL]")
        print(f"Old Uncompressed JSON: {t_old*1000:.2f} ms ({old_size/1024:.1f} KB)")
        print(f"New Gzip (.json.gz):   {t_new*1000:.2f} ms ({gz_size/1024:.1f} KB)")
        print(f"Disk Compression Ratio: {old_size/gz_size:.2f}x smaller | Storage Saved: {reduction_pct:.1f}%")

        assert gz_size < old_size / 5  # At least 5x smaller!


def run_phase3_vectorized_normalization_benchmark():
    payload = generate_synthetic_dhan_response(15000)
    
    # Old candle-by-candle iteration
    t0 = time.perf_counter()
    times = payload["data"]["start_Time"]
    opens = payload["data"]["open"]
    highs = payload["data"]["high"]
    lows = payload["data"]["low"]
    closes = payload["data"]["close"]
    vols = payload["data"]["volume"]
    ois = payload["data"]["oi"]
    ivs = payload["data"]["iv"]
    spots = payload["data"]["spot"]
    
    records = []
    for i in range(len(times)):
        c = CanonicalOptionCandle(
            timestamp=str(times[i]),
            timestamp_utc=1609473000 + i,
            symbol="NIFTY",
            relative_strike="ATM",
            option_type="CALL",
            spot_price=spots[i],
            open=opens[i],
            high=highs[i],
            low=lows[i],
            close=closes[i],
            volume=vols[i],
            open_interest=ois[i],
            implied_volatility=ivs[i]
        )
        records.append(c.to_dict())
    table_old = pa.Table.from_pylist(records, schema=CANONICAL_OPTION_SCHEMA)
    t_old = time.perf_counter() - t0

    # New vectorized PyArrow Table direct normalization
    t1 = time.perf_counter()
    table_new = DataNormalizer.normalize_dhan_payload_vectorized(payload, "NIFTY", "ATM", "CALL")
    t_new = time.perf_counter() - t1

    speedup = t_old / max(t_new, 1e-6)

    print(f"\n[PHASE 3 BENCHMARK - VECTORIZED NORMALIZATION]")
    print(f"Old Iterative Normalization: {t_old*1000:.2f} ms ({table_old.num_rows} rows)")
    print(f"New Vectorized PyArrow:     {t_new*1000:.2f} ms ({table_new.num_rows} rows)")
    print(f"Normalization Speedup:       {speedup:.2f}x faster")

    assert table_new.num_rows == 15000
    assert speedup > 1.5


def run_amendment_metrics_benchmark():
    engine = HistoricalBackfillEngine(max_workers=2)
    assert engine.raw_queue.maxsize == 100
    engine.progress["completed"] = 50
    engine._latencies = [0.25, 0.30, 0.20]
    engine._save_progress()
    
    with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
        p_data = json.load(f)

    metrics = p_data.get("performance_metrics", {})
    print(f"\n[AMENDMENT 5 BENCHMARK - ENHANCED PROGRESS METRICS]")
    print(f"Progress Metrics: {json.dumps(metrics, indent=2)}")

    assert "avg_req_per_sec" in metrics
    assert "cpu_percent" in metrics
    assert "ram_percent" in metrics
    engine.stop_async_writer()


if __name__ == "__main__":
    run_phase1_json_gzip_benchmark()
    run_phase3_vectorized_normalization_benchmark()
    run_amendment_metrics_benchmark()
    print("\nALL ARCHITECT AMENDMENT BENCHMARKS PASSED SUCCESSFULLY!")
