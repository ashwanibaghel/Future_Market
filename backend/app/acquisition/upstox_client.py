import time
import json
import random
import logging
import threading
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger("acquisition.upstox_client")


class TokenBucket:
    """Thread-safe Token Bucket Rate Limiter enforcing client-side HTTP request caps."""

    def __init__(self, rate_per_sec: float = 5.0):
        self.rate = rate_per_sec
        self.capacity = rate_per_sec
        self.tokens = rate_per_sec
        self.last_update = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self):
        """Blocks thread-safely until a token is available to enforce rate limit."""
        while True:
            with self.lock:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.last_update = now
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
            time.sleep(0.05)


class UpstoxApiClient:
    """
    Rate-limit-aware Upstox REST API Client.
    Handles Token Bucket rate limiting, exponential backoff with jitter, and date window pagination.
    """

    def __init__(self, access_token: Optional[str] = None, rate_limit_per_sec: float = 5.0):
        self.access_token = access_token
        self.rate_limiter = TokenBucket(rate_limit_per_sec)
        self.base_url = "https://api.upstox.com/v2"

    def fetch_historical_candles(
        self,
        instrument_key: str,
        interval: str = "1minute",
        to_date: str = "",
        from_date: str = "",
        max_retries: int = 5,
    ) -> List[List[Any]]:
        """
        Fetches historical candle array for instrument_key within a single date window (max 30 days).
        """
        encoded_key = urllib.parse.quote(instrument_key)
        endpoint = f"{self.base_url}/historical-candle/{encoded_key}/{interval}/{to_date}/{from_date}"

        headers = {
            "Accept": "application/json",
            "User-Agent": "OI-Lens-Acquisition-Engine/1.0",
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        attempt = 0
        while attempt < max_retries:
            attempt += 1
            self.rate_limiter.acquire()

            req = urllib.request.Request(endpoint, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    if resp.status == 200:
                        body = resp.read().decode("utf-8")
                        parsed = json.loads(body)
                        candles = parsed.get("data", {}).get("candles", [])
                        return candles
            except urllib.error.HTTPError as he:
                if he.code == 429 or he.code >= 500:
                    wait_time = (2 ** attempt) + random.uniform(0.1, 0.5)
                    logger.warning("Upstox HTTP %d on attempt %d for %s. Retrying in %.2fs", he.code, attempt, instrument_key, wait_time)
                    time.sleep(wait_time)
                else:
                    logger.error("Upstox HTTP %d Error for %s: %s", he.code, instrument_key, he.reason)
                    raise
            except Exception as exc:
                wait_time = (2 ** attempt) + random.uniform(0.1, 0.5)
                logger.warning("Upstox request exception on attempt %d: %s. Retrying in %.2fs", attempt, str(exc), wait_time)
                time.sleep(wait_time)

        raise RuntimeError(f"Exhausted max retries ({max_retries}) fetching historical candles for {instrument_key}")

    def fetch_multi_month_candles(
        self,
        instrument_key: str,
        start_date: str,
        end_date: str,
        interval: str = "1minute",
    ) -> List[List[Any]]:
        """
        Paginates a multi-month date range into 30-day non-overlapping windows and fetches all candles.
        """
        dt_start = datetime.strptime(start_date, "%Y-%m-%d")
        dt_end = datetime.strptime(end_date, "%Y-%m-%d")

        all_candles: List[List[Any]] = []
        curr_start = dt_start

        while curr_start <= dt_end:
            curr_end = min(curr_start + timedelta(days=29), dt_end)
            from_str = curr_start.strftime("%Y-%m-%d")
            to_str = curr_end.strftime("%Y-%m-%d")

            logger.info("Fetching %s candles for %s from %s to %s", interval, instrument_key, from_str, to_str)
            chunk_candles = self.fetch_historical_candles(
                instrument_key=instrument_key,
                interval=interval,
                to_date=to_str,
                from_date=from_str,
            )
            all_candles.extend(chunk_candles)
            curr_start = curr_end + timedelta(days=1)

        # Deduplicate and sort candles by timestamp descending/ascending
        seen = set()
        unique_candles = []
        for c in all_candles:
            ts = c[0]
            if ts not in seen:
                seen.add(ts)
                unique_candles.append(c)

        return sorted(unique_candles, key=lambda x: x[0])
