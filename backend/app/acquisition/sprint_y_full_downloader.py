"""
Sprint Y — High-Speed Multi-Threaded 5-Year NIFTY + BANKNIFTY Downloader
WITH: OI, IV, Strike, Spot (correct requiredData + CE/PE parser fix)
Uses ThreadPoolExecutor for 6x speedup.
Full resume support — skips valid existing files.
"""

import os
import gzip
import json
import time
import requests
import logging
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── CONFIG ──────────────────────────────────────────────────────────────────
DHAN_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzg1MjUwNDk5LCJpYXQiOjE3ODUxNjQwOTksInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTEyODI5NDIwIn0.YLp44QgIFPv8Lls2ennpFLoiIo_T-DmrAlODTY_lZP5Ps-aRXEk__GiOS79Oam--Ef9pfR8R4snjPa0E2k4LgA"
BASE_URL   = "https://api.dhan.co/v2"
OUTPUT_DIR = "E:/Future Stock/research_storage/raw/dhan_v2"
PROGRESS_FILE = "E:/Future Stock/research_storage/raw/dhan_v2_progress.json"

SECURITY_IDS = {"NIFTY": "13", "BANKNIFTY": "25"}
SYMBOLS      = ["NIFTY", "BANKNIFTY"]
OPTION_TYPES = ["CALL", "PUT"]
ATM_OFFSETS  = (
    ["ATM-10","ATM-9","ATM-8","ATM-7","ATM-6","ATM-5",
     "ATM-4","ATM-3","ATM-2","ATM-1","ATM",
     "ATM+1","ATM+2","ATM+3","ATM+4","ATM+5",
     "ATM+6","ATM+7","ATM+8","ATM+9","ATM+10"]
)
REQUIRED_DATA = ["open","high","low","close","iv","volume","strike","oi","spot"]

START_MONTH = date(2021, 1, 1)
END_MONTH   = date(2026, 7, 1)

MAX_WORKERS = 6
MAX_RETRIES = 3
RETRY_SLEEP = 3

os.makedirs(OUTPUT_DIR, exist_ok=True)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(threadName)s] %(levelname)s: %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("dhan_downloader")

HEADERS = {
    "access-token": DHAN_TOKEN,
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def get_option_data(data, opt_type):
    data_obj = data.get("data") or {}
    if opt_type == "PUT":
        return data_obj.get("pe") or {}
    else:
        return data_obj.get("ce") or {}

def has_oi_data(data, opt_type):
    opt_data = get_option_data(data, opt_type)
    oi = opt_data.get("oi", []) or []
    return any(x and x != 0 for x in oi)

def file_exists_and_valid(symbol, strike_str, opt_type, year, month):
    strike_fname = strike_str.replace("+", "+").replace("-", "-")
    out_dir = os.path.join(OUTPUT_DIR, str(year), f"{month:02d}")
    fname = f"{symbol}_{strike_fname}_{opt_type}_{year}-{month:02d}.json.gz"
    fpath = os.path.join(out_dir, fname)
    if not os.path.exists(fpath) or os.path.getsize(fpath) < 100:
        return False
    try:
        with gzip.open(fpath, "rt", encoding="utf-8") as f:
            d = json.load(f)
        opt_data = get_option_data(d, opt_type)
        return isinstance(opt_data, dict) and len(opt_data.get("timestamp", [])) > 0
    except Exception:
        return False

def save_file(data, symbol, strike_str, opt_type, year, month):
    strike_fname = strike_str.replace("+", "+").replace("-", "-")
    out_dir = os.path.join(OUTPUT_DIR, str(year), f"{month:02d}")
    os.makedirs(out_dir, exist_ok=True)
    fname = f"{symbol}_{strike_fname}_{opt_type}_{year}-{month:02d}.json.gz"
    fpath = os.path.join(out_dir, fname)
    with gzip.open(fpath, "wt", encoding="utf-8") as f:
        json.dump(data, f)
    return fpath

def fetch_and_save_task(job):
    symbol, strike_str, opt_type, year, month = job

    if file_exists_and_valid(symbol, strike_str, opt_type, year, month):
        return ("SKIPPED", symbol, strike_str, opt_type, year, month, 0, True)

    month_start = date(year, month, 1)
    if month < 12:
        month_end = date(year, month+1, 1) - timedelta(days=1)
    else:
        month_end = date(year, 12, 31)

    payload = {
        "exchangeSegment": "NSE_FNO",
        "instrument":      "OPTIDX",
        "securityId":      SECURITY_IDS[symbol],
        "interval":        "1",
        "strike":          strike_str,
        "drvOptionType":   opt_type,
        "expiryFlag":      "MONTH",
        "expiryCode":      1,
        "requiredData":    REQUIRED_DATA,
        "fromDate":        month_start.strftime("%Y-%m-%d"),
        "toDate":          month_end.strftime("%Y-%m-%d"),
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.post(
                f"{BASE_URL}/charts/rollingoption",
                json=payload, headers=HEADERS, timeout=25
            )
            r.raise_for_status()
            data = r.json()
            save_file(data, symbol, strike_str, opt_type, year, month)
            
            opt_data = get_option_data(data, opt_type)
            n_candles = len(opt_data.get("timestamp", []))
            oi_ok = has_oi_data(data, opt_type)
            return ("DOWNLOADED", symbol, strike_str, opt_type, year, month, n_candles, oi_ok)
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_SLEEP)
            else:
                return ("FAILED", symbol, strike_str, opt_type, year, month, 0, False)

def main():
    months = []
    cur = START_MONTH
    while cur <= END_MONTH:
        months.append((cur.year, cur.month))
        cur = cur + relativedelta(months=1)

    jobs = []
    for year, month in months:
        for symbol in SYMBOLS:
            for strike_str in ATM_OFFSETS:
                for opt_type in OPTION_TYPES:
                    jobs.append((symbol, strike_str, opt_type, year, month))

    total_jobs = len(jobs)
    log.info("=" * 60)
    log.info("HIGH-SPEED MULTI-THREADED 5-YEAR DOWNLOADER (WORKERS=%d)", MAX_WORKERS)
    log.info("Total Jobs: %d API calls", total_jobs)
    log.info("Estimated Time: ~5-7 minutes")
    log.info("=" * 60)

    start_time = time.time()
    completed = 0
    downloaded = 0
    skipped = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_and_save_task, job): job for job in jobs}
        
        for future in as_completed(futures):
            completed += 1
            status, symbol, strike_str, opt_type, year, month, n_candles, oi_ok = future.result()
            
            if status == "SKIPPED":
                skipped += 1
            elif status == "DOWNLOADED":
                downloaded += 1
            else:
                failed += 1

            if completed % 50 == 0 or status == "DOWNLOADED":
                elapsed = time.time() - start_time
                pct = (completed / total_jobs) * 100
                rate = completed / elapsed if elapsed > 0 else 0
                eta_sec = (total_jobs - completed) / rate if rate > 0 else 0
                log.info(
                    "[%d/%d - %.1f%%] %s %s %s %d/%02d | status=%s candles=%d OI=%s | ETA: %.1f min",
                    completed, total_jobs, pct,
                    symbol, strike_str, opt_type, year, month,
                    status, n_candles, "YES" if oi_ok else "NO",
                    eta_sec / 60
                )

    total_time = time.time() - start_time
    log.info("=" * 60)
    log.info("ALL JOBS FINISHED IN %.2f MINUTES!", total_time / 60)
    log.info("Downloaded : %d files", downloaded)
    log.info("Skipped    : %d files", skipped)
    log.info("Failed     : %d files", failed)
    log.info("=" * 60)

if __name__ == "__main__":
    main()
