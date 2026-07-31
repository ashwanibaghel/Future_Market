import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union
import pyarrow as pa
import pyarrow.parquet as pq

from app.research_os.governance.dataset_registry import PARQUET_LAKE_DIR
from app.research_os.feature_store.feature_store import FeatureStore
from app.research_os.feature_store.feature_version import DEFAULT_FEATURE_VERSION, DEFAULT_FEATURE_SCHEMA_VERSION
from app.research_os.features.calculators.base import BaseFeatureCalculator
from app.research_os.features.calculators.option_pcr import OptionPCRCalculator
from app.research_os.features.calculators.option_buildup import OptionBuildupCalculator
from app.research_os.features.calculators.spot_vwap import SpotVWAPCalculator

logger = logging.getLogger("research_os.features.engine")


class FeatureEngine:
    """
    Modular Quantitative Feature Engine Orchestrator.
    Executes independent feature calculator modules (PCR, OI Buildup, VWAP, Max Pain, etc.).
    Integrated with FeatureStore to enforce: "Compute once, reuse everywhere".
    """

    def __init__(
        self,
        feature_store: Optional[FeatureStore] = None,
        calculators: Optional[List[BaseFeatureCalculator]] = None,
    ):
        self.store = feature_store or FeatureStore()
        self.calculators = calculators or [
            OptionPCRCalculator(),
            OptionBuildupCalculator(),
            SpotVWAPCalculator(),
        ]

    def get_or_compute_features(
        self,
        symbol: str,
        year: Union[int, str],
        month: Union[int, str],
        feature_version: str = DEFAULT_FEATURE_VERSION,
    ) -> pa.Table:
        """
        Computes features once and caches them in the FeatureStore.
        Subsequent calls serve directly from FeatureStore without recomputation.
        """
        if self.store.has_features(symbol, year, month, feature_version):
            logger.info("FeatureStore CACHE HIT: Serving features for %s %s-%02d (%s)", symbol, year, int(month), feature_version)
            cached = self.store.get_features(symbol, year, month, feature_version)
            if cached is not None:
                return cached

        logger.info("FeatureStore CACHE MISS: Computing features for %s %s-%02d (%s)", symbol, year, int(month), feature_version)
        computed_table = self.compute_features_from_lake(symbol, year, month, feature_version)
        self.store.save_features(computed_table, symbol, year, month, feature_version)
        return computed_table

    def compute_features_from_lake(
        self,
        symbol: str,
        year: Union[int, str],
        month: Union[int, str],
        feature_version: str = DEFAULT_FEATURE_VERSION,
    ) -> pa.Table:
        """Reads canonical month Parquet partition and executes active feature calculators."""
        m_str = f"{int(month):02d}"
        partition_file = os.path.join(
            PARQUET_LAKE_DIR,
            "exchange=NSE_FO",
            f"symbol={symbol.upper()}_OPTIONS",
            f"year={year}",
            f"month={m_str}",
            "option_chain.parquet"
        )

        if not os.path.exists(partition_file):
            logger.warning("Canonical partition not found: %s", partition_file)
            return pa.Table.from_batches([])

        pf = pq.ParquetFile(partition_file)
        canonical_table = pf.read()
        return self._orchestrate_calculators(canonical_table, symbol.upper(), feature_version)

    def _orchestrate_calculators(self, canonical_table: pa.Table, symbol: str, feature_version: str) -> pa.Table:
        """Executes all modular calculators over canonical snapshot records."""
        if canonical_table.num_rows == 0:
            return pa.Table.from_batches([])

        p_dict = canonical_table.to_pydict()
        timestamps = p_dict["timestamp"]
        ts_utcs = p_dict["timestamp_utc"]
        rel_strikes = p_dict["relative_strike"]
        opt_types = p_dict["option_type"]
        spots = p_dict["spot_price"]
        closes = p_dict["close"]
        volumes = p_dict["volume"]
        ois = p_dict["open_interest"]

        # Group data by timestamp
        snapshots = {}
        n = len(timestamps)
        for i in range(n):
            ts = timestamps[i]
            if ts not in snapshots:
                snapshots[ts] = {
                    "ts_utc": ts_utcs[i],
                    "spot": spots[i],
                    "ce_vol": 0,
                    "pe_vol": 0,
                    "ce_oi": 0,
                    "pe_oi": 0,
                    "ce_close": 0.0,
                    "pe_close": 0.0,
                }
            s = snapshots[ts]
            opt = opt_types[i]
            if opt == "CALL":
                s["ce_vol"] += volumes[i]
                s["ce_oi"] += ois[i]
                if rel_strikes[i] == "ATM":
                    s["ce_close"] = closes[i]
            elif opt == "PUT":
                s["pe_vol"] += volumes[i]
                s["pe_oi"] += ois[i]
                if rel_strikes[i] == "ATM":
                    s["pe_close"] = closes[i]

        sorted_ts = sorted(snapshots.keys())

        columns = {
            "timestamp": [],
            "timestamp_utc": [],
            "symbol": [],
            "spot_price": [],
            "atm_strike": [],
            "feature_version": [],
            "schema_version": [],
        }

        # Initialize columns for each calculator
        for calc in self.calculators:
            for f in calc.output_fields:
                columns[f.name] = []

        hist_ctx = {}
        prev_ce_oi = 0
        prev_pe_oi = 0

        for ts in sorted_ts:
            s = snapshots[ts]
            spot = s["spot"]
            atm = float(round(spot / 50.0) * 50.0)

            hist_ctx["prev_ce_oi"] = prev_ce_oi
            hist_ctx["prev_pe_oi"] = prev_pe_oi

            columns["timestamp"].append(ts)
            columns["timestamp_utc"].append(s["ts_utc"])
            columns["symbol"].append(symbol)
            columns["spot_price"].append(spot)
            columns["atm_strike"].append(atm)
            columns["feature_version"].append(feature_version)
            columns["schema_version"].append(DEFAULT_FEATURE_SCHEMA_VERSION)

            # Run each modular calculator
            for calc in self.calculators:
                res = calc.compute(s, hist_ctx)
                for k, v in res.items():
                    columns[k].append(v)

            prev_ce_oi = s["ce_oi"]
            prev_pe_oi = s["pe_oi"]

        arrays = [pa.array(v) for v in columns.values()]
        field_names = list(columns.keys())
        return pa.Table.from_arrays(arrays, names=field_names)
