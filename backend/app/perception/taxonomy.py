"""
Sprint Z — Artificial Market Perception Engine v1
Observation Taxonomy & Schema Definitions.

Defines standard MECE (Mutually Exclusive, Collectively Exhaustive) observation categories,
strict 5-point severity levels, and structured explainable Observation schemas.
"""

from enum import Enum
from typing import Dict, Any, List
from dataclasses import dataclass, asdict

class ObservationCategory(str, Enum):
    OPEN_INTEREST    = "OPEN_INTEREST"     # Put/Call Writing, Buildups, Unwinding
    VOLUME           = "VOLUME"            # Volume Spikes, Volume Skew
    PRICE_STRUCTURE  = "PRICE_STRUCTURE"   # Drift, Range, Breakouts
    VOLATILITY       = "VOLATILITY"        # IV Expansion, IV Crush
    ATM_SHIFT        = "ATM_SHIFT"         # ATM Migration Up/Down
    KEY_LEVELS       = "KEY_LEVELS"        # Call Walls, Put Floors
    EXPIRY_BEHAVIOUR = "EXPIRY_BEHAVIOUR"  # Expiry Acceleration, Gamma Risk

class SeverityLevel(str, Enum):
    LEVEL_1_LOW      = "LEVEL_1_LOW"       # Minor noise / background signal (Scale: 1)
    LEVEL_2_MODERATE = "LEVEL_2_MODERATE"  # Moderate trend or accumulation (Scale: 2)
    LEVEL_3_HIGH     = "LEVEL_3_HIGH"      # Significant flow / heavy writing (Scale: 3)
    LEVEL_4_CRITICAL = "LEVEL_4_CRITICAL"  # Level breach / sharp unwinding (Scale: 4)
    LEVEL_5_EXTREME  = "LEVEL_5_EXTREME"   # Panic / Anomaly / Gamma Squeeze (Scale: 5)

SEVERITY_NUMERIC_MAP = {
    SeverityLevel.LEVEL_1_LOW: 1,
    SeverityLevel.LEVEL_2_MODERATE: 2,
    SeverityLevel.LEVEL_3_HIGH: 3,
    SeverityLevel.LEVEL_4_CRITICAL: 4,
    SeverityLevel.LEVEL_5_EXTREME: 5,
}

@dataclass
class Observation:
    observation_id: str          # e.g., "OBS_PUT_WRITING_AGGRESSIVE"
    category: str                # ObservationCategory
    confidence: float            # 0.0 to 1.0 confidence score
    severity: str                # SeverityLevel string
    severity_numeric: int        # 1 to 5 integer for quantitative modeling
    description: str             # Human-readable discretionary trader observation
    evidence: Dict[str, Any]     # 100% Explainable quantitative evidence metrics

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

# ── TAXONOMY REGISTRY OF RECOGNIZED OBSERVATION TYPES ───────────────────────
OBSERVATION_TAXONOMY = {
    "OBS_PUT_WRITING_AGGRESSIVE": {
        "category": ObservationCategory.OPEN_INTEREST,
        "description": "Aggressive Put Writing detected at ATM/ITM strikes indicating strong institutional support."
    },
    "OBS_CALL_WRITING_AGGRESSIVE": {
        "category": ObservationCategory.OPEN_INTEREST,
        "description": "Aggressive Call Writing detected at ATM/OTM strikes indicating strong overhead resistance."
    },
    "OBS_LONG_BUILDUP": {
        "category": ObservationCategory.OPEN_INTEREST,
        "description": "Long Buildup confirmed: Spot rising with expanding Open Interest."
    },
    "OBS_SHORT_BUILDUP": {
        "category": ObservationCategory.OPEN_INTEREST,
        "description": "Short Buildup confirmed: Spot falling with expanding Open Interest."
    },
    "OBS_SHORT_COVERING": {
        "category": ObservationCategory.OPEN_INTEREST,
        "description": "Short Covering rally detected: Spot rising while Open Interest contracts."
    },
    "OBS_LONG_UNWINDING": {
        "category": ObservationCategory.OPEN_INTEREST,
        "description": "Long Unwinding sell-off detected: Spot falling while Open Interest contracts."
    },
    "OBS_PCR_EXPANSION": {
        "category": ObservationCategory.VOLUME,
        "description": "Put-Call Ratio (PCR) expanding rapidly above bullish threshold."
    },
    "OBS_PCR_CONTRACTION": {
        "category": ObservationCategory.VOLUME,
        "description": "Put-Call Ratio (PCR) contracting rapidly below bearish threshold."
    },
    "OBS_CALL_WALL_STRENGTHENING": {
        "category": ObservationCategory.KEY_LEVELS,
        "description": "Call Wall strengthening with fresh OI accumulation at resistance strike."
    },
    "OBS_PUT_FLOOR_STRENGTHENING": {
        "category": ObservationCategory.KEY_LEVELS,
        "description": "Put Floor strengthening with fresh OI accumulation at support strike."
    },
    "OBS_CALL_WALL_BREACH": {
        "category": ObservationCategory.KEY_LEVELS,
        "description": "Call Wall breached: Spot price traded above major Call Wall strike."
    },
    "OBS_PUT_FLOOR_BREACH": {
        "category": ObservationCategory.KEY_LEVELS,
        "description": "Put Floor breached: Spot price traded below major Put Floor strike."
    },
    "OBS_ATM_UPSHIFT": {
        "category": ObservationCategory.ATM_SHIFT,
        "description": "ATM strike shifted higher following upward spot momentum."
    },
    "OBS_ATM_DOWNSHIFT": {
        "category": ObservationCategory.ATM_SHIFT,
        "description": "ATM strike shifted lower following downward spot momentum."
    },
    "OBS_IV_EXPANSION": {
        "category": ObservationCategory.VOLATILITY,
        "description": "Implied Volatility expanding significantly across option strikes."
    },
    "OBS_IV_CRUSH": {
        "category": ObservationCategory.VOLATILITY,
        "description": "Implied Volatility collapsing sharply following event completion."
    },
    "OBS_EXPIRY_GAMMA_ACCELERATION": {
        "category": ObservationCategory.EXPIRY_BEHAVIOUR,
        "description": "Near-expiry Gamma Acceleration detected with heightened pin risk."
    }
}
