"""
Sprint AA — Market Situation Understanding Engine v1
Taxonomy, Evolution Phases, and 4-Pillar Market Context Definitions.

📜 THE CONSTITUTION LINE (NON-NEGOTIABLE RULE):
"The Situation Engine shall never directly infer trading decisions.
Its only responsibility is to answer: 'What is happening in the market right now?' NOT 'What should I do?'"
"""

from enum import Enum
from typing import Dict, Any, List
from dataclasses import dataclass, field, asdict

class EvolutionPhase(str, Enum):
    BUILDING     = "BUILDING"      # Initial emergence of supporting observations
    SUSTAINED    = "SUSTAINED"     # Persistence over 2-3 consecutive timestamps
    ACCELERATING = "ACCELERATING"  # Expanding severity, volume, or momentum
    WEAKENING    = "WEAKENING"     # Diminishing supporting evidence / early deceleration
    DISSIPATING  = "DISSIPATING"   # Transitioning back to baseline or new situation

class TrendPillar(str, Enum):
    UPWARD_DRIFT      = "UPWARD_DRIFT"
    DOWNWARD_PRESSURE = "DOWNWARD_PRESSURE"
    SIDEWAYS_FLAT     = "SIDEWAYS_FLAT"

class VolatilityPillar(str, Enum):
    EXPANDING   = "EXPANDING"
    COMPRESSING = "COMPRESSING"
    STABLE      = "STABLE"

class ParticipationPillar(str, Enum):
    HIGH_INSTITUTIONAL = "HIGH_INSTITUTIONAL"
    MODERATE_RETAIL    = "MODERATE_RETAIL"
    THIN_FLOW          = "THIN_FLOW"

class StructurePillar(str, Enum):
    ACCULATION        = "ACCUMULATION"
    DISTRIBUTION        = "DISTRIBUTION"
    TRENDING            = "TRENDING"
    RANGE_COMPRESSION   = "RANGE_COMPRESSION"
    EXPANSION_BREAKOUT  = "EXPANSION_BREAKOUT"
    EXPIRY_PINNING      = "EXPIRY_PINNING"

@dataclass
class MarketContext:
    trend: str          # TrendPillar
    volatility: str     # VolatilityPillar
    participation: str  # ParticipationPillar
    structure: str      # StructurePillar

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class Situation:
    situation_id: str                   # e.g., "SIT_ACCUMULATION_BEHAVIOUR"
    evolution_phase: str                # EvolutionPhase
    confidence: float                   # Multi-factor confidence score (0.0 to 1.0)
    severity: str                       # Severity string (e.g. LEVEL_3_HIGH)
    severity_level: int                 # 1 to 5 integer
    start_time: str                     # ISO timestamp
    peak_time: str                      # ISO timestamp
    latest_time: str                    # ISO timestamp
    duration_minutes: int               # Duration in minutes
    why: List[str]                      # Deprecated summary list (retained for backward compatibility)
    reasoning: str                      # Explicit Cognitive Reasoning string
    unknowns: List[str]                 # Explicit list of inconclusive or missing data points
    supporting_observations: List[str]  # List of Observation IDs
    market_context: Dict[str, str]      # 4-pillar market context dict
    evidence: Dict[str, Any]            # Quantitative evidence metrics

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

# ── DESCRIPTIVE MARKET SITUATION TAXONOMY REGISTRY ──────────────────────────
SITUATION_TAXONOMY = {
    "SIT_ACCUMULATION_BEHAVIOUR": {
        "description": "Institutional Accumulation: Persistent Put Writing combined with ATM up-shift and PCR expansion.",
        "default_structure": StructurePillar.ACCULATION
    },
    "SIT_DISTRIBUTION_BEHAVIOUR": {
        "description": "Institutional Distribution: Persistent Call Writing combined with ATM down-shift and PCR contraction.",
        "default_structure": StructurePillar.DISTRIBUTION
    },
    "SIT_CONSOLIDATION_COMPRESSION": {
        "description": "Consolidation Compression: Stable price structure within tight boundary walls/floors.",
        "default_structure": StructurePillar.RANGE_COMPRESSION
    },
    "SIT_LEVEL_BREACH_EXPANSION": {
        "description": "Level Breach Expansion: Spot price actively breaching major Call Wall or Put Floor with volume displacement.",
        "default_structure": StructurePillar.EXPANSION_BREAKOUT
    },
    "SIT_SHORT_COVERING_MOMENTUM": {
        "description": "Short Covering Momentum: Spot rising while Call Open Interest unwinds rapidly.",
        "default_structure": StructurePillar.TRENDING
    },
    "SIT_LONG_LIQUIDATION_PRESSURE": {
        "description": "Long Liquidation Pressure: Spot falling while Put Open Interest unwinds rapidly.",
        "default_structure": StructurePillar.TRENDING
    },
    "SIT_LIQUIDITY_VACUUM_DISPLACEMENT": {
        "description": "Liquidity Vacuum Displacement: Rapid price displacement across strikes due to order book thinning.",
        "default_structure": StructurePillar.EXPANSION_BREAKOUT
    },
    "SIT_EXPIRY_PINNING_CLUSTER": {
        "description": "Expiry Pinning Cluster: Spot price pinned near high Open Interest strike on expiry date.",
        "default_structure": StructurePillar.EXPIRY_PINNING
    }
}
