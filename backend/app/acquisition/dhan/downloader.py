import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from app.acquisition.dhan.config import DhanConfig, UNDERLYING_SECURITY_IDS
from app.acquisition.dhan.client import DhanApiClient

logger = logging.getLogger("acquisition.dhan.downloader")


class RollingStrikeDownloader:
    """
    Downloads time-series candles for a single relative strike (e.g. ATM, ATM+1)
    and paginates across multi-month date ranges in 30-day windows.
    """

    def __init__(self, client: Optional[DhanApiClient] = None):
        self.client = client or DhanApiClient()

    def fetch_strike_candles_window(
        self,
        symbol: str,
        strike: str,
        option_type: str,
        from_date: str,
        to_date: str,
        interval: int = 1,
        expiry_flag: str = "MONTH",
    ) -> List[Dict[str, Any]]:
        """
        Fetches 1-minute historical candles for a single strike within a 30-day date window.
        """
        sec_id = UNDERLYING_SECURITY_IDS.get(symbol.upper(), "13")
        payload = {
            "exchangeSegment": "NSE_FNO",
            "instrument": "OPTIDX",
            "securityId": sec_id,
            "interval": interval,
            "strike": strike.upper(),
            "drvOptionType": option_type.upper(),
            "expiryFlag": expiry_flag.upper(),
            "expiryCode": 1,
            "requiredData": [
                "open", "high", "low", "close", "volume",
                "open_interest", "implied_volatility", "spot_price"
            ],
            "fromDate": from_date,
            "toDate": to_date,
        }

        try:
            resp = self.client.post("/charts/rollingoption", payload)
            return self.parse_raw_rolling_response(resp)
        except Exception as exc:
            logger.error("Failed to fetch rolling option for %s %s %s (%s to %s): %s", symbol, strike, option_type, from_date, to_date, str(exc))
            return []

    def parse_raw_rolling_response(self, resp: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parses raw Dhan rolling option response into structured candle dictionaries."""
        data = resp.get("data", {})
        if not data:
            return []

        # If wrapped inside 'ce' or 'pe' subdict
        if isinstance(data, dict):
            if "ce" in data and isinstance(data["ce"], dict):
                data = data["ce"]
            elif "pe" in data and isinstance(data["pe"], dict):
                data = data["pe"]

        records = []
        if isinstance(data, list):
            for row in data:
                if len(row) >= 5:
                    records.append({
                        "timestamp": str(row[0]),
                        "open": float(row[1]),
                        "high": float(row[2]),
                        "low": float(row[3]),
                        "close": float(row[4]),
                        "volume": int(row[5]) if len(row) > 5 else 0,
                        "open_interest": int(row[6]) if len(row) > 6 else 0,
                        "implied_volatility": float(row[7]) if len(row) > 7 else 0.0,
                        "spot_price": float(row[8]) if len(row) > 8 else 0.0,
                    })
        elif isinstance(data, dict):
            times = data.get("start_Time", []) or data.get("timestamp", []) or data.get("time", [])
            opens = data.get("open", [])
            highs = data.get("high", [])
            lows = data.get("low", [])
            closes = data.get("close", [])
            vols = data.get("volume", [0] * len(times))
            ois = data.get("oi", []) or data.get("open_interest", [0] * len(times))
            ivs = data.get("iv", []) or data.get("implied_volatility", [0.0] * len(times))
            spots = data.get("spot", []) or data.get("spot_price", [0.0] * len(times))

            for i in range(len(times)):
                records.append({
                    "timestamp": str(times[i]),
                    "open": float(opens[i]) if i < len(opens) else 0.0,
                    "high": float(highs[i]) if i < len(highs) else 0.0,
                    "low": float(lows[i]) if i < len(lows) else 0.0,
                    "close": float(closes[i]) if i < len(closes) else 0.0,
                    "volume": int(vols[i]) if i < len(vols) else 0,
                    "open_interest": int(ois[i]) if i < len(ois) else 0,
                    "implied_volatility": float(ivs[i]) if i < len(ivs) else 0.0,
                    "spot_price": float(spots[i]) if i < len(spots) else 0.0,
                })

        return records

    def fetch_multi_month_strike(
        self,
        symbol: str,
        strike: str,
        option_type: str,
        start_date: str,
        end_date: str,
        interval: int = 1,
        expiry_flag: str = "MONTH",
    ) -> List[Dict[str, Any]]:
        """
        Paginates a multi-month range into 30-day date windows and fetches all candles.
        """
        dt_start = datetime.strptime(start_date, "%Y-%m-%d")
        dt_end = datetime.strptime(end_date, "%Y-%m-%d")

        all_records: List[Dict[str, Any]] = []
        curr_start = dt_start

        while curr_start <= dt_end:
            curr_end = min(curr_start + timedelta(days=29), dt_end)
            from_str = curr_start.strftime("%Y-%m-%d")
            to_str = curr_end.strftime("%Y-%m-%d")

            chunk_records = self.fetch_strike_candles_window(
                symbol=symbol,
                strike=strike,
                option_type=option_type,
                from_date=from_str,
                to_date=to_str,
                interval=interval,
                expiry_flag=expiry_flag,
            )
            all_records.extend(chunk_records)
            curr_start = curr_end + timedelta(days=1)

        # Deduplicate and sort by timestamp
        seen = set()
        unique = []
        for r in all_records:
            ts = r["timestamp"]
            if ts not in seen:
                seen.add(ts)
                unique.append(r)

        return sorted(unique, key=lambda x: x["timestamp"])
