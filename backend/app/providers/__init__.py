from app.providers.base import BaseProvider
from app.providers.nse_provider import NSEProvider

# Dynamic Provider Factory
def get_provider(provider_name: str) -> BaseProvider:
    provider_name = provider_name.upper()
    if provider_name == "NSE":
        return NSEProvider()
    elif provider_name == "UPSTOX":
        # Placeholder for Upstox integration
        raise NotImplementedError("Upstox Provider is not implemented yet")
    elif provider_name == "ANGEL":
        # Placeholder for Angel One integration
        raise NotImplementedError("Angel Provider is not implemented yet")
    else:
        raise ValueError(f"Unknown provider type: {provider_name}")
