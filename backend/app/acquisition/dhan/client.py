import time
import json
import random
import logging
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional

from app.acquisition.dhan.config import DhanConfig
from app.acquisition.dhan.auth import DhanAuthenticator, DhanAuthError
from app.acquisition.upstox_client import TokenBucket

logger = logging.getLogger("acquisition.dhan.client")


class DhanApiError(Exception):
    """Base exception for DhanHQ API failures."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[Any] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class DhanRateLimitError(DhanApiError):
    """Raised when rate limits are exceeded (HTTP 429)."""
    pass


class DhanApiClient:
    """
    Rate-limited DhanHQ HTTP API Client with exponential backoff and jitter.
    """

    def __init__(self, config: Optional[DhanConfig] = None):
        self.config = config or DhanConfig.from_env()
        self.authenticator = DhanAuthenticator(self.config)
        self.rate_limiter = TokenBucket(self.config.rate_limit_per_sec)

    def post(self, endpoint_path: str, payload: Dict[str, Any], max_retries: int = 5) -> Dict[str, Any]:
        """
        Executes an authenticated HTTP POST request to DhanHQ API.
        """
        url = f"{self.config.base_url.rstrip('/')}/{endpoint_path.lstrip('/')}"
        headers = self.authenticator.get_auth_headers()
        json_bytes = json.dumps(payload).encode("utf-8")

        attempt = 0
        while attempt < max_retries:
            attempt += 1
            self.rate_limiter.acquire()

            req = urllib.request.Request(url, data=json_bytes, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                    body = resp.read().decode("utf-8")
                    return json.loads(body)
            except urllib.error.HTTPError as he:
                body_err = he.read().decode("utf-8") if he.fp else ""
                try:
                    parsed_err = json.loads(body_err)
                except Exception:
                    parsed_err = body_err

                if he.code == 429:
                    wait_time = (2 ** attempt) + random.uniform(0.1, 0.5)
                    logger.warning("DhanHQ HTTP 429 Rate Limit on attempt %d for %s. Retrying in %.2fs", attempt, url, wait_time)
                    time.sleep(wait_time)
                    if attempt == max_retries:
                        raise DhanRateLimitError("DhanHQ HTTP 429 Rate Limit Exceeded", status_code=429, response_body=parsed_err)
                elif he.code >= 500:
                    wait_time = (2 ** attempt) + random.uniform(0.1, 0.5)
                    logger.warning("DhanHQ HTTP %d Gateway Error on attempt %d. Retrying in %.2fs", he.code, attempt, wait_time)
                    time.sleep(wait_time)
                    if attempt == max_retries:
                        raise DhanApiError(f"DhanHQ Server Error (HTTP {he.code})", status_code=he.code, response_body=parsed_err)
                else:
                    logger.error("DhanHQ HTTP %d Error: %s", he.code, body_err)
                    raise DhanApiError(f"DhanHQ HTTP {he.code}: {he.reason}", status_code=he.code, response_body=parsed_err)
            except Exception as exc:
                if isinstance(exc, (DhanApiError, DhanAuthError)):
                    raise exc
                wait_time = (2 ** attempt) + random.uniform(0.1, 0.5)
                logger.warning("DhanHQ Connection Error on attempt %d: %s. Retrying in %.2fs", attempt, str(exc), wait_time)
                time.sleep(wait_time)
                if attempt == max_retries:
                    raise DhanApiError(f"DhanHQ Connection Error: {str(exc)}")

        raise DhanApiError("Exhausted maximum HTTP retries")
