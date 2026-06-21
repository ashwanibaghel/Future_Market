from typing import Dict, Any

class BaseProvider:
    async def fetch_option_chain(self, symbol: str) -> Dict[str, Any]:
        """
        Fetches option chain raw data for the specified symbol.
        Returns a dictionary with parsed strikes, spot price, expiry dates, etc.
        """
        raise NotImplementedError("Providers must implement fetch_option_chain")
