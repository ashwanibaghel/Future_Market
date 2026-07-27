from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class CanonicalOptionCandle:
    timestamp: str
    timestamp_utc: int
    symbol: str
    relative_strike: str
    option_type: str
    spot_price: float
    open: float
    high: float
    low: float
    close: float
    volume: int
    open_interest: int
    implied_volatility: float
    provider: str = "DHAN"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "timestamp_utc": self.timestamp_utc,
            "symbol": self.symbol,
            "relative_strike": self.relative_strike,
            "option_type": self.option_type,
            "spot_price": self.spot_price,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "open_interest": self.open_interest,
            "implied_volatility": self.implied_volatility,
            "provider": self.provider,
        }


class DataNormalizer:
    """
    Decouples market data providers (Dhan, Upstox, TruData) from OI Lens core storage.
    Normalizes provider-specific payloads into CanonicalOptionCandle objects.
    """

    @staticmethod
    def normalize_dhan_record(
        raw_record: Dict[str, Any],
        symbol: str,
        relative_strike: str,
        option_type: str,
        timestamp_utc: int,
    ) -> CanonicalOptionCandle:
        """Translates a raw Dhan record dictionary into a CanonicalOptionCandle."""
        return CanonicalOptionCandle(
            timestamp=str(raw_record["timestamp"]),
            timestamp_utc=timestamp_utc,
            symbol=symbol.upper(),
            relative_strike=relative_strike.upper(),
            option_type=option_type.upper(),
            spot_price=float(raw_record.get("spot_price", 0.0)),
            open=float(raw_record["open"]),
            high=float(raw_record["high"]),
            low=float(raw_record["low"]),
            close=float(raw_record["close"]),
            volume=int(raw_record.get("volume", 0)),
            open_interest=int(raw_record.get("open_interest", 0)),
            implied_volatility=float(raw_record.get("implied_volatility", 0.0)),
            provider="DHAN",
        )
