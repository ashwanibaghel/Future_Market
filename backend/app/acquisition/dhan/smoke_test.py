import os
import json
import time
import logging
from datetime import datetime, timezone, timedelta

from app.acquisition.dhan.config import DhanConfig
from app.acquisition.dhan.auth import DhanAuthenticator
from app.acquisition.dhan.client import DhanApiClient
from app.acquisition.dhan.downloader import RollingStrikeDownloader
from app.acquisition.dhan.chain_builder import HistoricalOptionChainBuilder

logger = logging.getLogger("acquisition.dhan.smoke_test")


def run_production_smoke_test() -> dict:
    """
    Executes a production smoke test for the DhanHQ Acquisition Engine.
    """
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "environment_configured": False,
        "api_connectivity": "FAILED",
        "http_status": None,
        "sample_rows_returned": 0,
        "latency_ms": 0.0,
        "field_validations": {},
        "parquet_stored": False,
        "error": None,
    }

    config = DhanConfig.from_env()
    if not config.is_configured():
        report["error"] = "DhanHQ credentials (DHAN_CLIENT_ID / DHAN_ACCESS_TOKEN) are missing from environment."
        return report

    report["environment_configured"] = True

    client = DhanApiClient(config)
    downloader = RollingStrikeDownloader(client)

    # 1-minute ATM CALL sample fetch for NIFTY
    today = datetime.now()
    to_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    from_date = (today - timedelta(days=5)).strftime("%Y-%m-%d")

    t0 = time.time()
    try:
        candles = downloader.fetch_strike_candles_window(
            symbol="NIFTY",
            strike="ATM",
            option_type="CALL",
            from_date=from_date,
            to_date=to_date,
            interval=1
        )
        latency = (time.time() - t0) * 1000.0
        report["latency_ms"] = round(latency, 2)
        report["api_connectivity"] = "SUCCESS"
        report["http_status"] = 200
        report["sample_rows_returned"] = len(candles)

        if candles:
            sample = candles[0]
            report["field_validations"] = {
                "timestamp_present": "timestamp" in sample and bool(sample["timestamp"]),
                "open_present": "open" in sample and isinstance(sample["open"], float),
                "high_present": "high" in sample and isinstance(sample["high"], float),
                "low_present": "low" in sample and isinstance(sample["low"], float),
                "close_present": "close" in sample and isinstance(sample["close"], float),
                "volume_present": "volume" in sample and isinstance(sample["volume"], int),
                "open_interest_present": "open_interest" in sample and isinstance(sample["open_interest"], int),
                "implied_volatility_present": "implied_volatility" in sample and isinstance(sample["implied_volatility"], float),
                "spot_price_present": "spot_price" in sample and isinstance(sample["spot_price"], float),
            }

            # Store sample dataset in Parquet Lake
            builder = HistoricalOptionChainBuilder(downloader=downloader)
            res_store = builder.build_option_chain_dataset(
                symbol="NIFTY",
                start_date=from_date,
                end_date=to_date,
                relative_strikes=["ATM"],
                dataset_version="DS-SMOKE-v1.0.0"
            )
            report["parquet_stored"] = res_store.get("success", False)
            report["dataset_id"] = res_store.get("dataset_id")

    except Exception as exc:
        report["latency_ms"] = round((time.time() - t0) * 1000.0, 2)
        report["error"] = str(exc)

    return report


if __name__ == "__main__":
    rep = run_production_smoke_test()
    print(json.dumps(rep, indent=2))
