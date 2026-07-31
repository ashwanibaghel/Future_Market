"""
Sprint AD — Experience Synthesis Engine v1
Taxonomy, Synthesis Schema, and Hypothesis Definitions.

📜 THE CONSTITUTION LINE (ARTICLE VI & VIII):
"Evidence -> Confidence (NEVER Confidence -> Evidence).
Decision -> Outcome -> Learning."
"""

import hashlib
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

def generate_synthesis_id(exchange: str, asset: str, symbol: str, start_iso: str) -> str:
    """
    Generates a globally unique Synthesis ID:
    SYN_{EXCHANGE}_{ASSET}_{SYMBOL}_{YYYYMMDDTHHMMSS}_{HASH6}
    """
    ts_clean = start_iso.replace("-", "").replace(":", "").replace(".000Z", "").replace("Z", "")
    raw_key = f"SYN_{exchange}_{asset}_{symbol}_{start_iso}".encode("utf-8")
    hash_prefix = hashlib.sha256(raw_key).hexdigest()[:6].upper()
    return f"SYN_{exchange.upper()}_{asset.upper()}_{symbol.upper()}_{ts_clean}_{hash_prefix}"

@dataclass
class EmpiricalEvidence:
    sample_size: int
    supporting_memories: int
    contradicting_memories: int
    raw_success_rate_pct: float
    importance_weighted_success_rate_pct: float
    average_favourable_excursion_pct: float
    average_adverse_excursion_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ContradictionSummary:
    contradicting_memories_count: int
    largest_failure_cluster: str
    failure_frequency: str
    common_trigger: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class UnknownsAssessment:
    unknowns_list: List[str]
    unknown_coverage_pct: float
    unknown_impact: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ExperienceSynthesis:
    synthesis_id: str
    primary_situation: str
    symbol: str
    exchange: str
    timestamp: str
    empirical_evidence: Dict[str, Any]
    contradiction_summary: Dict[str, Any]
    unknowns_assessment: Dict[str, Any]
    structural_hypothesis: str
    certainty_level: str
    statistical_warning: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
