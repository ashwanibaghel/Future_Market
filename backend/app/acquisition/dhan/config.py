import os
from dataclasses import dataclass
from typing import Dict, Optional

DHAN_BASE_URL = "https://api.dhan.co/v2"

# Security IDs mapping for Dhan F&O
UNDERLYING_SECURITY_IDS: Dict[str, str] = {
    "NIFTY": "13",
    "BANKNIFTY": "25",
    "FINNIFTY": "27",
}

# Standard 21 relative strikes range (-10 to +10)
DEFAULT_RELATIVE_STRIKES = [
    f"ATM-{i}" for i in range(10, 0, -1)
] + ["ATM"] + [
    f"ATM+{i}" for i in range(1, 11)
]


@dataclass
class DhanConfig:
    client_id: str
    access_token: str
    base_url: str = DHAN_BASE_URL
    rate_limit_per_sec: float = 8.0
    timeout_seconds: int = 15

    @classmethod
    def from_env(cls) -> "DhanConfig":
        client_id = os.environ.get("DHAN_CLIENT_ID", "").strip()
        access_token = os.environ.get("DHAN_ACCESS_TOKEN", "").strip()
        return cls(client_id=client_id, access_token=access_token)

    def is_configured(self) -> bool:
        return bool(self.client_id and self.access_token)
