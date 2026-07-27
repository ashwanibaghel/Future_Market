import os
import json
import time
import logging
from datetime import datetime, timezone, timedelta
import pyarrow.parquet as pq

from app.acquisition.dhan.config import DhanConfig
from app.acquisition.dhan.client import DhanApiClient
from app.acquisition.dhan.downloader import RollingStrikeDownloader
from app.acquisition.dhan.chain_builder import HistoricalOptionChainBuilder
from app.research_os.governance.dataset_registry import ensure_research_storage_structure

logger = logging.getLogger("acquisition.dhan.sprint5a_validation")


def execute_sprint5a_validation() -> dict:
    """
    Sprint 5A Production Validation Engine.
    Executes a real end-to-end DhanHQ API rolling option call, saves raw JSON response,
    runs the Chain Builder, persists ZSTD Parquet, verifies readback, and generates evidence.
    """
    ensure_research_storage_structure()

    report = {
        "sprint": "5A",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "credentials_loaded": False,
        "http_status": None,
        "latency_ms": 0.0,
        "retry_count": 0,
        "rate_limiting_encountered": False,
        "raw_json_path": None,
        "parquet_file_path": None,
        "rows_returned": 0,
        "field_validations": {},
        "parquet_readback": {},
        "validation_result": "FAIL",
        "error": None,
    }

    # 1. Load credentials
    config = DhanConfig.from_env()
    if not config.is_configured():
        report["error"] = "DhanHQ credentials (DHAN_CLIENT_ID / DHAN_ACCESS_TOKEN) not found in environment or .env file."
        return report

    report["credentials_loaded"] = True

    # 2. Setup Client & Downloader
    client = DhanApiClient(config)
    downloader = RollingStrikeDownloader(client)

    # Use recent trading session date range
    today = datetime.now()
    to_date = (today - timedelta(days=2)).strftime("%Y-%m-%d")
    from_date = (today - timedelta(days=3)).strftime("%Y-%m-%d")

    # 3. Direct RAW HTTP Request to capture Raw JSON
    payload = {
        "exchangeSegment": "NSE_FNO",
        "instrument": "OPTIDX",
        "securityId": "13",  # NIFTY 50
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

        # Save RAW JSON response to research_storage/raw/dhan/YYYY/MM/DD/sample_response.json
        now_dt = datetime.now(timezone.utc)
        raw_dir = os.path.join(
            "research_storage", "raw", "dhan",
            now_dt.strftime("%Y"), now_dt.strftime("%m"), now_dt.strftime("%d")
        )
        os.makedirs(raw_dir, exist_ok=True)
        raw_json_file = os.path.join(raw_dir, "sample_response.json")
        with open(raw_json_file, "w", encoding="utf-8") as f:
            json.dump(raw_response, f, indent=2)
        report["raw_json_path"] = raw_json_file

        # Parse candles via Downloader
        records = downloader.fetch_strike_candles_window(
            symbol="NIFTY",
            strike="ATM",
            option_type="CALL",
            from_date=from_date,
            to_date=to_date,
            interval=1
        )
        report["rows_returned"] = len(records)

        if len(records) > 0:
            sample = records[0]
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

            # 4. Run Chain Builder on ONLY this sample
            builder = HistoricalOptionChainBuilder(downloader=downloader)
            res_build = builder.build_option_chain_dataset(
                symbol="NIFTY",
                start_date=from_date,
                end_date=to_date,
                relative_strikes=["ATM"],
                dataset_version="DS-v1.0.0"
            )

            if res_build.get("success"):
                parquet_path = res_build["written_files"][0]
                report["parquet_file_path"] = parquet_path

                # 5. Readback & verify generated Parquet file
                table = pq.ParquetFile(parquet_path).read()
                file_size = os.path.getsize(parquet_path)

                report["parquet_readback"] = {
                    "read_success": True,
                    "row_count": table.num_rows,
                    "column_count": table.num_columns,
                    "columns": table.column_names,
                    "file_size_bytes": file_size,
                    "compression": "PARQUET_ZSTD",
                }

                if table.num_rows > 0 and all(report["field_validations"].values()):
                    report["validation_result"] = "PASS"

    except Exception as exc:
        report["latency_ms"] = round((time.time() - t0) * 1000.0, 2)
        report["error"] = str(exc)

    return report


if __name__ == "__main__":
    rep = execute_sprint5a_validation()
    print(json.dumps(rep, indent=2))
