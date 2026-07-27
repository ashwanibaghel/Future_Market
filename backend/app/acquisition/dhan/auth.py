from typing import Dict
from app.acquisition.dhan.config import DhanConfig


class DhanAuthError(Exception):
    """Raised when Dhan authentication credentials are invalid or missing."""
    pass


class DhanAuthenticator:
    """Manages DhanHQ HTTP Request authentication headers."""

    def __init__(self, config: DhanConfig):
        self.config = config

    def get_auth_headers(self) -> Dict[str, str]:
        """Generates HTTP headers required by DhanHQ API."""
        if not self.config.is_configured():
            raise DhanAuthError("DhanHQ credentials (DHAN_CLIENT_ID / DHAN_ACCESS_TOKEN) are missing.")

        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "OI-Lens-Dhan-Engine/1.0",
            "access-token": self.config.access_token,
            "client-id": self.config.client_id,
        }
