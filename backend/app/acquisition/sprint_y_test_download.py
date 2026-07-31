"""
Sprint Y — Dhan Re-Download: Test with 1 month data
Tests correct requiredData: ["open","high","low","close","iv","volume","strike","oi","spot"]
Month: January 2023, Symbol: NIFTY
"""
import os
import gzip
import json
import time
import requests
from datetime import datetime, timedelta

# --- CONFIG ---
DHAN_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzg1MjUwNDk5LCJpYXQiOjE3ODUxNjQwOTksInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTEyODI5NDIwIn0.YLp44QgIFPv8Lls2ennpFLoiIo_T-DmrAlODTY_lZP5Ps-aRXEk__GiOS79Oam--Ef9pfR8R4snjPa0E2k4LgA"
BASE_URL = "https://api.dhan.co/v2"

# Dhan security IDs
SECURITY_IDS = {"NIFTY": "13", "BANKNIFTY": "25"}

# ATM offsets to download
ATM_OFFSETS = [f"ATM{i:+d}" for i in range(-10, 11)]  # ATM-10 to ATM+10
OPTION_TYPES = ["CALL", "PUT"]

OUTPUT_DIR = "E:/Future Stock/research_storage/raw/dhan_v2"
os.makedirs(OUTPUT_DIR, exist_ok=True)

HEADERS = {
    "access-token": DHAN_TOKEN,
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def fetch_rolling_option(symbol, strike, option_type, from_date, to_date, expiry_flag="MONTH"):
    payload = {
        "exchangeSegment": "NSE_FNO",
        "instrument": "OPTIDX",
        "securityId": SECURITY_IDS[symbol],
        "interval": "1",
        "strike": strike,
        "drvOptionType": option_type,
        "expiryFlag": expiry_flag,
        "expiryCode": 1,
        "requiredData": ["open", "high", "low", "close", "iv", "volume", "strike", "oi", "spot"],
        "fromDate": from_date,
        "toDate": to_date,
    }
    resp = requests.post(f"{BASE_URL}/charts/rollingoption", json=payload, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()

def check_response_quality(data):
    """Check if OI, IV, Spot are actually populated"""
    ce = (data.get("data") or {}).get("ce") or {}
    if not ce:
        return {"has_oi": False, "has_iv": False, "has_spot": False, "has_strike": False, "candles": 0}
    
    timestamps = ce.get("timestamp", []) or []
    oi = ce.get("oi", []) or []
    iv = ce.get("iv", []) or []
    spot = ce.get("spot", []) or []
    strike = ce.get("strike", []) or []
    
    non_zero_oi = sum(1 for x in oi if x and x != 0)
    non_zero_iv = sum(1 for x in iv if x and x != 0)
    non_zero_spot = sum(1 for x in spot if x and x != 0)
    
    return {
        "candles": len(timestamps),
        "oi_count": len(oi),
        "iv_count": len(iv),
        "spot_count": len(spot),
        "strike_count": len(strike),
        "has_oi": non_zero_oi > 0,
        "has_iv": non_zero_iv > 0,
        "has_spot": non_zero_spot > 0,
        "has_strike": len(strike) > 0,
        "sample_oi": oi[:3] if oi else [],
        "sample_iv": iv[:3] if iv else [],
        "sample_spot": spot[:3] if spot else [],
        "sample_strike": strike[:3] if strike else [],
    }

print("=" * 60)
print("  TEST DOWNLOAD — JANUARY 2023, NIFTY")
print("  requiredData: open, high, low, close, iv, volume, strike, oi, spot")
print("=" * 60)

# Test with just 3 strikes first
test_strikes = ["ATM-1", "ATM", "ATM+1"]
test_results = {}

for strike in test_strikes:
    for opt_type in ["CALL", "PUT"]:
        print(f"\n  Fetching NIFTY {strike} {opt_type} | Jan 2023...")
        try:
            resp = fetch_rolling_option(
                symbol="NIFTY",
                strike=strike,
                option_type=opt_type,
                from_date="2023-01-01",
                to_date="2023-01-31",
                expiry_flag="MONTH"
            )
            quality = check_response_quality(resp)
            key = f"NIFTY_{strike}_{opt_type}"
            test_results[key] = quality
            
            print(f"    Candles:  {quality['candles']}")
            print(f"    OI data:  {'YES ✓' if quality['has_oi'] else 'NO ✗'} (count={quality['oi_count']}, sample={quality['sample_oi']})")
            print(f"    IV data:  {'YES ✓' if quality['has_iv'] else 'NO ✗'} (count={quality['iv_count']}, sample={quality['sample_iv']})")
            print(f"    Spot:     {'YES ✓' if quality['has_spot'] else 'NO ✗'} (sample={quality['sample_spot']})")
            print(f"    Strike:   {'YES ✓' if quality['has_strike'] else 'NO ✗'} (sample={quality['sample_strike']})")
            
            # Save this test file
            out_dir = f"{OUTPUT_DIR}/2023/01/01"
            os.makedirs(out_dir, exist_ok=True)
            out_file = f"{out_dir}/NIFTY_{strike}_{opt_type}_2023-01-01.json.gz"
            with gzip.open(out_file, 'wt', encoding='utf-8') as f:
                json.dump(resp, f)
            print(f"    Saved: {out_file}")
            
            time.sleep(0.5)  # rate limit
            
        except Exception as e:
            print(f"    ERROR: {e}")

print("\n" + "=" * 60)
print("  QUALITY SUMMARY")
print("=" * 60)
has_oi_any = any(v["has_oi"] for v in test_results.values())
has_iv_any = any(v["has_iv"] for v in test_results.values())
has_spot_any = any(v["has_spot"] for v in test_results.values())

print(f"  OI data in response:    {'YES - FULL DOWNLOAD READY!' if has_oi_any else 'NO - API not returning OI'}")
print(f"  IV data in response:    {'YES - FULL DOWNLOAD READY!' if has_iv_any else 'NO - API not returning IV'}")
print(f"  Spot in response:       {'YES - FULL DOWNLOAD READY!' if has_spot_any else 'NO'}")

if has_oi_any and has_iv_any:
    print("\n  DATA IS GOOD! Full 5-year re-download can begin.")
else:
    print("\n  WARNING: OI/IV missing. Check API token or endpoint params.")
print("=" * 60)
