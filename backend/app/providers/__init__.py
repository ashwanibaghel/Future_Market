from app.providers.base import BaseProvider
from app.providers.nse_provider import NSEProvider
from app.providers.upstox_provider import UpstoxProvider

# Dynamic Provider Factory
def get_provider(provider_name: str) -> BaseProvider:
    provider_name = provider_name.upper()
    if provider_name == "NSE":
        return NSEProvider()
    elif provider_name == "UPSTOX":
        return UpstoxProvider()
    elif provider_name == "ANGEL":
        # Placeholder for Angel One integration
        raise NotImplementedError("Angel Provider is not implemented yet")
    else:
        raise ValueError(f"Unknown provider type: {provider_name}")
