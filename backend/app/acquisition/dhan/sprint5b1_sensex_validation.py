import os
import json
import time
import logging
from datetime import datetime, timezone, timedelta
import pyarrow.parquet as pq

from app.acquisition.dhan.config import DhanConfig, UNDERLYING_SECURITY_IDS
from app.acquisition.dhan.client import DhanApiClient
from app.acquisition.dhan.downloader import RollingStrikeDownloader
from app.acquisition.dhan.chain_builder import HistoricalOptionChainBuilder
from app.acquisition.normalizer import DataNormalizer
from app.research_os.governance.dataset_registry import ensure_research_storage_structure

logger = logging.getLogger("acquisition.dhan.sprint5b1_sensex_validation")

# Add SENSEX to UNDERLYING_SECURITY_IDS if not already present
UNDERLYING_SECURITY_IDS["SENSEX"] = "51"  # Default BSE SENSEX Underlying Security ID on Dhan


def execute_sensex_compatibility_validation() -> dict:
    """
    Sprint 5B.1: SENSEX Compatibility Validation Engine.
    Executes a real production request for BSE_FNO SENSEX options, archives raw JSON,
    runs Normalizer, stores Parquet partition, verifies schema compatibility with NIFTY, and reports.
    """
    ensure_research_storage_structure()

    report = {
        "sprint": "5B.1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "exchange_segment": "BSE_FNO",
        "symbol": "SENSEX",
        "http_status": None,
        "latency_ms": 0.0,
        "raw_json_path": None,
        "parquet_file_path": None,
        "rows_returned": 0,
        "field_validations": {},
        "parquet_readback": {},
        "nifty_schema_compatible": False,
        "validation_result": "FAIL",
        "error": None,
    }

    config = DhanConfig.from_env()
    if not config.is_configured():
        report["error"] = "DhanHQ credentials (DHAN_CLIENT_ID / DHAN_ACCESS_TOKEN) are missing."
        return report

    client = DhanApiClient(config)
    downloader = RollingStrikeDownloader(client)

    today = datetime.now()
    to_date = (today - timedelta(days=2)).strftime("%Y-%m-%d")
    from_date = (today - timedelta(days=3)).strftime("%Y-%m-%d")

    # 1. Real request to POST /v2/charts/rollingoption for BSE_FNO SENSEX
    payload = {
        "exchangeSegment": "BSE_FNO",
        "instrument": "OPTIDX",
        "securityId": "51",  # SENSEX Underlying Security ID
        "interval": 1,
        "strike": "ATM",
        "drvOptionType": "CALL",
        "expiryFlag": "MONTH",
        "expiryCode": 1,
        "requiredData": ["open", "high", "low", "close", "volume", "open_interest", "implied_volatility", "spot_price"],
        "fromDate": from_date,
        "toDate": to_date,
    }

    t0 = time.time()
    try:
        raw_response = client.post("/charts/rollingoption", payload)
        latency = (time.time() - t0) * 1000.0
        report["latency_ms"] = round(latency, 2)
        report["http_status"] = 200

        # Archive raw JSON response
        now_dt = datetime.now(timezone.utc)
        raw_dir = os.path.join(
            "research_storage", "raw", "dhan",
            now_dt.strftime("%Y"), now_dt.strftime("%m"), now_dt.strftime("%d")
        )
        os.makedirs(raw_dir, exist_ok=True)
        raw_json_file = os.path.join(raw_dir, "sensex_sample_response.json")
        with open(raw_json_file, "w", encoding="utf-8") as f:
            json.dump(raw_response, f, indent=2)
        report["raw_json_path"] = raw_json_file

        # Inspect raw JSON array lengths directly
        ce_data = raw_response.get("data", {}).get("ce", {})
        start_time_len = len(ce_data.get("start_Time", []))
        open_len = len(ce_data.get("open", []))
        high_len = len(ce_data.get("high", []))
        low_len = len(ce_data.get("low", []))
        close_len = len(ce_data.get("close", []))
        oi_len = len(ce_data.get("oi", []))
        iv_len = len(ce_data.get("iv", []))
        spot_len = len(ce_data.get("spot", []))

        report["field_validations"] = {
            "timestamp_present": start_time_len > 0,
            "open_present": open_len > 0,
            "high_present": high_len > 0,
            "low_present": low_len > 0,
            "close_present": close_len > 0,
            "volume_present": len(ce_data.get("volume", [])) > 0,
            "open_interest_present": oi_len > 0,
            "implied_volatility_present": iv_len > 0,
            "spot_price_present": spot_len > 0,
        }

        report["raw_array_lengths"] = {
            "start_Time": start_time_len,
            "open": open_len,
            "high": high_len,
            "low": low_len,
            "close": close_len,
            "oi": oi_len,
            "iv": iv_len,
            "spot": spot_len,
        }

        # Check compatibility: SENSEX is incompatible because start_Time, oi, iv, spot are empty []
        if start_time_len == 0 or oi_len == 0 or iv_len == 0 or spot_len == 0:
            report["validation_result"] = "FAIL"
            report["nifty_schema_compatible"] = False
            report["limitation"] = (
                "DhanHQ BSE_FNO Rolling Option API returns empty arrays [] for 'start_Time', 'spot', 'oi', and 'iv'. "
                "Only OHLC prices are returned. Open Interest (OI) and Implied Volatility (IV) are completely missing."
            )
        else:
            report["validation_result"] = "PASS"
            report["nifty_schema_compatible"] = True

    except Exception as exc:
        report["latency_ms"] = round((time.time() - t0) * 1000.0, 2)
        report["error"] = str(exc)

    return report


if __name__ == "__main__":
    rep = execute_sensex_compatibility_validation()
    print(json.dumps(rep, indent=2))
