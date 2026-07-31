import os
import json
import time
import gzip
import logging
import queue
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import pyarrow as pa
import pyarrow.parquet as pq
try:
    import psutil
except ImportError:
    psutil = None

from app.acquisition.normalizer import DataNormalizer, CanonicalOptionCandle, CANONICAL_OPTION_SCHEMA
from app.acquisition.dhan.config import DhanConfig, DEFAULT_RELATIVE_STRIKES, UNDERLYING_SECURITY_IDS
from app.acquisition.dhan.client import DhanApiClient
from app.acquisition.dhan.downloader import RollingStrikeDownloader
from app.acquisition.validator import DataQualityAuditor
from app.acquisition.replay_indexer import ReplayIndexBuilder
from app.research_os.governance.versioning import build_provenance_header, calculate_file_sha256, DEFAULT_DATASET_VERSION
from app.research_os.governance.dataset_registry import (
    DatasetRegistry,
    PARQUET_LAKE_DIR,
    CHECKSUMS_DIR,
    QUALITY_REPORTS_DIR,
    RESEARCH_STORAGE_DIR,
    ensure_research_storage_structure,
)
from app.research_os.governance.quality_reporter import QualityReporter
from app.research_os.datalake.validator import ParquetDataValidator

logger = logging.getLogger("acquisition.engine")

PROGRESS_FILE = os.path.join(RESEARCH_STORAGE_DIR, "download_progress.json")
COVERAGE_REPORT_FILE = os.path.join(QUALITY_REPORTS_DIR, "coverage_report_2021_2026.json")
RAW_STORAGE_DIR = os.path.join(RESEARCH_STORAGE_DIR, "raw")


class HistoricalBackfillEngine:
    """
    Decoupled, High-Performance Resumable Historical Backfill Engine for 5-Year Option Data Lake.
    Architectural Amendments Applied:
    1. Adaptive Worker Benchmarking (Dynamic 1, 2, 4 worker selection)
    2. Reduced Queue Size (maxsize=100 for memory efficiency)
    3. Gzip Raw Archival (.json.gz compression)
    4. Month-Level Replay Index Generation
    5. Enhanced Performance Metrics in download_progress.json
    """

    def __init__(self, client: Optional[DhanApiClient] = None, max_workers: int = 2):
        ensure_research_storage_structure()
        os.makedirs(RAW_STORAGE_DIR, exist_ok=True)
        self.client = client or DhanApiClient()
        self.downloader = RollingStrikeDownloader(self.client)
        self.registry = DatasetRegistry()
        self.reporter = QualityReporter()
        self.indexer = ReplayIndexBuilder()
        self.max_workers = max_workers
        self.progress = self._load_progress()

        # Performance Tracking State
        self._start_time = time.perf_counter()
        self._latencies: List[float] = []

        # Amendment 2: Reduced Queue Size (maxsize=100) to prevent RAM spikes
        self.raw_queue: queue.Queue = queue.Queue(maxsize=100)
        self._stop_writer_event = threading.Event()
        self.writer_thread = threading.Thread(target=self._raw_writer_worker, daemon=True)
        self.writer_thread.start()

    def _raw_writer_worker(self):
        """Background worker thread for async raw gzip JSON archival."""
        while not self._stop_writer_event.is_set() or not self.raw_queue.empty():
            try:
                item = self.raw_queue.get(timeout=0.2)
                if item is None:
                    break
                provider, symbol, strike, opt_type, from_date, raw_payload = item
                self._save_raw_json_gzip(provider, symbol, strike, opt_type, from_date, raw_payload)
                self.raw_queue.task_done()
            except queue.Empty:
                continue
            except Exception as exc:
                logger.warning("Error in background raw gzip JSON writer: %s", str(exc))

    def _save_raw_json_gzip(self, provider: str, symbol: str, strike: str, opt_type: str, from_date: str, raw_payload: Dict[str, Any]):
        """Amendment 3: Compressed Raw JSON write as .json.gz file."""
        try:
            dt = datetime.strptime(from_date, "%Y-%m-%d")
            raw_dir = os.path.join(RAW_STORAGE_DIR, provider.lower(), dt.strftime("%Y"), dt.strftime("%m"), dt.strftime("%d"))
            os.makedirs(raw_dir, exist_ok=True)
            raw_file = os.path.join(raw_dir, f"{symbol}_{strike}_{opt_type}_{from_date}.json.gz")
            
            compact_json = json.dumps(raw_payload, separators=(',', ':')).encode('utf-8')
            compressed = gzip.compress(compact_json)
            with open(raw_file, "wb") as f:
                f.write(compressed)
        except Exception as exc:
            logger.warning("Failed saving raw compressed JSON: %s", str(exc))

    def queue_raw_json(self, provider: str, symbol: str, strike: str, opt_type: str, from_date: str, raw_payload: Dict[str, Any]):
        """Enqueue raw JSON response payload for async gzip writer."""
        try:
            self.raw_queue.put((provider, symbol, strike, opt_type, from_date, raw_payload), block=True, timeout=5.0)
        except queue.Full:
            self._save_raw_json_gzip(provider, symbol, strike, opt_type, from_date, raw_payload)

    def stop_async_writer(self):
        """Flushes queue and safely stops the background writer thread."""
        self.raw_queue.join()
        self._stop_writer_event.set()
        if self.writer_thread.is_alive():
            self.writer_thread.join(timeout=3.0)

    def _load_progress(self) -> Dict[str, Any]:
        """Loads progress state from download_progress.json if it exists."""
        if os.path.exists(PROGRESS_FILE):
            try:
                with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as exc:
                logger.warning("Failed to parse progress file: %s. Re-initializing.", str(exc))

        return {
            "completed": 0,
            "remaining": 0,
            "last_date": None,
            "last_symbol": None,
            "completed_chunks": [],
            "failed_chunks": [],
            "performance_metrics": {
                "avg_req_per_sec": 0.0,
                "avg_latency_ms": 0.0,
                "cpu_percent": 0.0,
                "ram_percent": 0.0,
            }
        }

    def _save_progress(self):
        """Amendment 5: Includes live CPU, RAM, Latency, and Req/Sec metrics in download_progress.json."""
        elapsed = max(0.1, time.perf_counter() - self._start_time)
        completed = self.progress["completed"]
        avg_req_sec = round(completed / elapsed, 2)
        avg_lat_ms = round(sum(self._latencies[-100:]) / max(1, len(self._latencies[-100:])) * 1000, 2) if self._latencies else 0.0

        try:
            cpu_pct = psutil.cpu_percent(interval=None)
            ram_pct = psutil.virtual_memory().percent
        except Exception:
            cpu_pct, ram_pct = 0.0, 0.0

        self.progress["performance_metrics"] = {
            "avg_req_per_sec": avg_req_sec,
            "avg_latency_ms": avg_lat_ms,
            "cpu_percent": cpu_pct,
            "ram_percent": ram_pct,
        }

        temp_file = PROGRESS_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(self.progress, f, indent=2)
        os.replace(temp_file, PROGRESS_FILE)

    def benchmark_optimal_workers(self, symbol: str = "NIFTY", sec_id: str = "13") -> int:
        """
        Amendment 1: Benchmark with 1, 2, and 4 workers on 4 sample strike calls.
        Chooses the fastest configuration that avoids throttling.
        """
        logger.info("Running adaptive worker benchmarking (1, 2, 4 workers)...")
        sample_tasks = [
            ("ATM", "CALL"), ("ATM", "PUT"),
            ("ATM+1", "CALL"), ("ATM+1", "PUT")
        ]
        from_str = "2021-01-01"
        to_str = "2021-01-30"

        best_workers = 2
        best_req_sec = 0.0

        for w in [1, 2, 4]:
            t0 = time.perf_counter()
            throttled = False
            try:
                with ThreadPoolExecutor(max_workers=w) as executor:
                    futures = [
                        executor.submit(self._fetch_single_strike_task, symbol, sec_id, strike, opt, from_str, to_str)
                        for strike, opt in sample_tasks
                    ]
                    for f in as_completed(futures):
                        res, lat = f.result()
                        if res is None:
                            throttled = True
            except Exception:
                throttled = True

            dur = time.perf_counter() - t0
            req_sec = len(sample_tasks) / max(dur, 0.01)
            logger.info("Worker Benchmark | Workers: %d | Time: %.2fs | Speed: %.2f req/s | Throttled: %s", w, dur, req_sec, throttled)

            if not throttled and req_sec > best_req_sec:
                best_req_sec = req_sec
                best_workers = w

        logger.info("Adaptive Benchmark Selected Optimal Workers: %d (Speed: %.2f req/s)", best_workers, best_req_sec)
        self.max_workers = best_workers
        return best_workers

    def _fetch_single_strike_task(
        self,
        symbol: str,
        sec_id: str,
        rel_strike: str,
        opt_type: str,
        from_str: str,
        to_str: str,
    ) -> tuple:
        """Fetches and normalizes a single strike task, returning (table, latency)."""
        payload = {
            "exchangeSegment": "NSE_FNO",
            "instrument": "OPTIDX",
            "securityId": sec_id,
            "interval": 1,
            "strike": rel_strike,
            "drvOptionType": opt_type,
            "expiryFlag": "MONTH",
            "expiryCode": 1,
            "requiredData": ["open", "high", "low", "close", "volume", "open_interest", "implied_volatility", "spot_price"],
            "fromDate": from_str,
            "toDate": to_str,
        }

        t0 = time.perf_counter()
        try:
            raw_res = self.client.post("/charts/rollingoption", payload)
            lat = time.perf_counter() - t0

            # Enqueue raw JSON for async gzip disk archival
            self.queue_raw_json("DHAN", symbol, rel_strike, opt_type, from_str, raw_res)

            # Vectorized PyArrow Table Construction
            table = DataNormalizer.normalize_dhan_payload_vectorized(raw_res, symbol, rel_strike, opt_type)
            return table, lat
        except Exception as exc:
            logger.warning("Fetch exception for %s %s %s (%s): %s", symbol, rel_strike, opt_type, from_str, str(exc))
            return None, time.perf_counter() - t0

    def execute_5year_backfill(
        self,
        symbols: List[str] = ["NIFTY", "BANKNIFTY"],
        start_year: int = 2021,
        end_year: int = 2026,
        relative_strikes: Optional[List[str]] = None,
        dataset_version: str = DEFAULT_DATASET_VERSION,
        adaptive_benchmark: bool = True,
    ) -> Dict[str, Any]:
        """
        Executes complete 5-year historical backfill using adaptive pipelined architecture.
        """
        strikes = relative_strikes or DEFAULT_RELATIVE_STRIKES
        option_types = ["CALL", "PUT"]

        if adaptive_benchmark:
            self.benchmark_optimal_workers(symbols[0])

        years = list(range(start_year, end_year + 1))
        total_months = len(years) * 12
        total_requests = len(symbols) * len(strikes) * len(option_types) * total_months
        self.progress["remaining"] = total_requests - self.progress["completed"]
        self._save_progress()

        request_counter = 0
        self._start_time = time.perf_counter()

        try:
            for symbol in symbols:
                sec_id = UNDERLYING_SECURITY_IDS.get(symbol.upper(), "13")
                for year in years:
                    for month in range(1, 13):
                        dt_start = datetime(year, month, 1)
                        if month == 12:
                            dt_end = datetime(year, 12, 31)
                        else:
                            dt_end = datetime(year, month + 1, 1) - timedelta(days=1)

                        if dt_start > datetime.now():
                            continue

                        from_str = dt_start.strftime("%Y-%m-%d")
                        to_str = dt_end.strftime("%Y-%m-%d")
                        month_str = f"{year}-{month:02d}"

                        partition_file = os.path.join(
                            PARQUET_LAKE_DIR,
                            "exchange=NSE_FO",
                            f"symbol={symbol}_OPTIONS",
                            f"year={year}",
                            f"month={month:02d}",
                            "option_chain.parquet"
                        )

                        chunk_key = f"{symbol}_{month_str}"
                        if chunk_key in self.progress["completed_chunks"] and os.path.exists(partition_file):
                            val = ParquetDataValidator.validate_file(partition_file)
                            if val["valid"]:
                                logger.info("Skipping verified partition %s", partition_file)
                                continue

                        month_tables: List[pa.Table] = []
                        task_configs = [(st, opt) for st in strikes for opt in option_types]

                        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                            future_to_task = {
                                executor.submit(
                                    self._fetch_single_strike_task,
                                    symbol, sec_id, rel_strike, opt_type, from_str, to_str
                                ): (rel_strike, opt_type)
                                for rel_strike, opt_type in task_configs
                            }

                            for future in as_completed(future_to_task):
                                rel_strike, opt_type = future_to_task[future]
                                request_counter += 1
                                self.progress["completed"] += 1
                                self.progress["remaining"] = max(0, total_requests - self.progress["completed"])
                                self.progress["last_date"] = from_str
                                self.progress["last_symbol"] = symbol

                                try:
                                    table, lat = future.result()
                                    self._latencies.append(lat)
                                    if table is not None:
                                        if table.num_rows > 0:
                                            month_tables.append(table)
                                    else:
                                        # Only append to failed_chunks if HTTP/connection actually failed (table is None)
                                        self.progress["failed_chunks"].append(f"{symbol}_{rel_strike}_{opt_type}_{from_str}")
                                except Exception as exc:
                                    logger.warning("Task execution failed for %s %s: %s", rel_strike, opt_type, str(exc))
                                    self.progress["failed_chunks"].append(f"{symbol}_{rel_strike}_{opt_type}_{from_str}")

                                if request_counter % 10 == 0:
                                    self._save_progress()
                                    logger.info("Progress checkpoint: %d/%d requests completed", self.progress["completed"], total_requests)

                        # Write Parquet Partition & Verify Integrity
                        if month_tables:
                            os.makedirs(os.path.dirname(partition_file), exist_ok=True)
                            concatenated_table = pa.concat_tables(month_tables)
                            pq.write_table(concatenated_table, partition_file, compression="zstd")

                            val_res = ParquetDataValidator.validate_file(partition_file)
                            if val_res["valid"]:
                                self.progress["completed_chunks"].append(chunk_key)

                                # Amendment 4: Build Replay Index only after month partition completes
                                try:
                                    self.indexer.build_index_for_lake()
                                except Exception as idx_exc:
                                    logger.warning("Failed building replay index for %s %d-%02d: %s", symbol, year, month, str(idx_exc))

                                self._save_progress()
                                logger.info("Rule 6 Pass: Verified month Parquet partition %s (%d rows)", partition_file, val_res["total_rows"])

        finally:
            self.stop_async_writer()

        coverage_report = self._generate_coverage_report(symbols, years)
        return {
            "status": "COMPLETED",
            "total_requests_completed": self.progress["completed"],
            "coverage_report": coverage_report,
        }

    def _generate_coverage_report(self, symbols: List[str], years: List[int]) -> Dict[str, Any]:
        """Rule 7: Generates Coverage Report (2021-2026 PASS/FAIL) across all years."""
        report = {"years": {}, "overall_status": "PASS"}

        for year in years:
            year_pass = True
            month_statuses = {}
            for month in range(1, 13):
                m_str = f"{month:02d}"
                found = False
                for symbol in symbols:
                    p_file = os.path.join(
                        PARQUET_LAKE_DIR,
                        "exchange=NSE_FO",
                        f"symbol={symbol}_OPTIONS",
                        f"year={year}",
                        f"month={m_str}",
                        "option_chain.parquet"
                    )
                    if os.path.exists(p_file):
                        val = ParquetDataValidator.validate_file(p_file)
                        if val["valid"]:
                            found = True
                            break
                status_str = "PASS" if found else "NO_DATA"
                month_statuses[m_str] = status_str
                if not found and year <= datetime.now().year:
                    year_pass = False

            report["years"][str(year)] = {
                "status": "PASS" if year_pass else "PARTIAL",
                "months": month_statuses,
            }

        with open(COVERAGE_REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        return report
