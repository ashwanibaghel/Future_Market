import pyarrow as pa
from typing import Dict, Any, List

BENCHMARK_FEATURE_SCHEMA = pa.schema([
    ("timestamp", pa.string()),
    ("timestamp_utc", pa.int64()),
    ("symbol", pa.string()),
    ("spot_price", pa.float64()),
    ("atm_strike", pa.float64()),
    ("pcr_volume", pa.float64()),
    ("pcr_oi", pa.float64()),
    ("oi_change_ce", pa.int64()),
    ("oi_change_pe", pa.int64()),
    ("vwap", pa.float64()),
    ("buildup_signal", pa.string()),
    ("feature_version", pa.string()),
    ("schema_version", pa.string()),
])


def generate_benchmark_dataset(num_snapshots: int = 50) -> pa.Table:
    """
    Requirement 7 Deterministic Benchmark Dataset Generator.
    Generates a deterministic synthetic feature dataset for regression testing.
    """
    timestamps = [f"2021-03-01T09:{i % 60:02d}:00+05:30" for i in range(num_snapshots)]
    ts_utcs = [1614570300 + (i * 60) for i in range(num_snapshots)]
    spots = [14500.0 + (i * 2.5) for i in range(num_snapshots)]
    pcr_vols = [1.35 if i % 2 == 0 else 0.65 for i in range(num_snapshots)]
    buildups = ["LONG_BUILDUP" if i % 2 == 0 else "SHORT_BUILDUP" for i in range(num_snapshots)]

    return pa.Table.from_arrays(
        [
            pa.array(timestamps, type=pa.string()),
            pa.array(ts_utcs, type=pa.int64()),
            pa.array(["NIFTY"] * num_snapshots, type=pa.string()),
            pa.array(spots, type=pa.float64()),
            pa.array([14500.0] * num_snapshots, type=pa.float64()),
            pa.array(pcr_vols, type=pa.float64()),
            pa.array([1.10] * num_snapshots, type=pa.float64()),
            pa.array([500] * num_snapshots, type=pa.int64()),
            pa.array([600] * num_snapshots, type=pa.int64()),
            pa.array([14505.0] * num_snapshots, type=pa.float64()),
            pa.array(buildups, type=pa.string()),
            pa.array(["F-v1.0.0"] * num_snapshots, type=pa.string()),
            pa.array(["FS-v1.0.0"] * num_snapshots, type=pa.string()),
        ],
        schema=BENCHMARK_FEATURE_SCHEMA,
    )
