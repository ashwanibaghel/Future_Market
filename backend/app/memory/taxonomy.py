"""
Sprint AB — Market Memory Formation Engine v1
Taxonomy, Memory Schema, Collision-Proof Hash ID Generator, and Outcome Types.

📜 THE CONSTITUTION LINE (ARTICLE IX - MEMORY IMMUTABILITY):
"Once a Market Memory Episode is created, its observed facts shall never be modified or rewritten.
Corrections, reinterpretations, or reflections must create new metadata objects, never rewrite history."
"""

import hashlib
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

def generate_memory_id(exchange: str, asset: str, symbol: str, start_iso: str) -> str:
    """
    Generates a globally unique, collision-proof Memory ID:
    MEM_{EXCHANGE}_{ASSET}_{SYMBOL}_{YYYYMMDDTHHMMSS}_{HASH6}
    """
    ts_clean = start_iso.replace("-", "").replace(":", "").replace(".000Z", "").replace("Z", "")
    raw_key = f"{exchange}_{asset}_{symbol}_{start_iso}".encode("utf-8")
    hash_prefix = hashlib.sha256(raw_key).hexdigest()[:6].upper()
    return f"MEM_{exchange.upper()}_{asset.upper()}_{symbol.upper()}_{ts_clean}_{hash_prefix}"

@dataclass
class MultiHorizonOutcome:
    horizon_5m: Dict[str, Any]
    horizon_15m: Dict[str, Any]
    horizon_30m: Dict[str, Any]
    horizon_60m: Dict[str, Any]
    horizon_eod: Dict[str, Any]
    horizon_next_day: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class MemoryReflection:
    expectation: str
    actual: str
    counterfactual: str
    lesson: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class EpisodicMemory:
    memory_id: str                      # Collision-proof ID
    memory_type: str                    # "EPISODIC_MEMORY"
    primary_situation: str              # e.g., "SIT_ACCUMULATION_BEHAVIOUR"
    symbol: str
    exchange: str
    start_time: str                     # ISO timestamp
    end_time: str                       # ISO timestamp
    duration_minutes: int               # Total dynamic state episode duration
    peak_confidence: float              # Max confidence achieved during episode
    key_reasoning: str                  # Core explainable reasoning
    unknowns: List[str]                 # Inconclusive data declarations
    features: Dict[str, Any]            # Dynamic extensible feature signature map
    episode_outcomes: Dict[str, Any]    # 6-horizon outcome dict (5m, 15m, 30m, 60m, EOD, NEXT_DAY)
    reflection: Dict[str, Any]          # Decoupled counterfactual reflection object

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
