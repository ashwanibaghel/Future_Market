"""
Sprint AE — Cognitive Reasoning Engine v1
Taxonomy, Competing Hypotheses Schema, and Reasoning Chain Definitions.

📜 THE CONSTITUTION LINE (ARTICLE VI & VIII):
"Evidence -> Confidence (NEVER Confidence -> Evidence).
Decision -> Outcome -> Learning."
"""

import hashlib
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

def generate_reasoning_id(exchange: str, asset: str, symbol: str, start_iso: str) -> str:
    """
    Generates a globally unique Reasoning ID:
    REASON_{EXCHANGE}_{ASSET}_{SYMBOL}_{YYYYMMDDTHHMMSS}_{HASH6}
    """
    ts_clean = start_iso.replace("-", "").replace(":", "").replace(".000Z", "").replace("Z", "")
    raw_key = f"REASON_{exchange}_{asset}_{symbol}_{start_iso}".encode("utf-8")
    hash_prefix = hashlib.sha256(raw_key).hexdigest()[:6].upper()
    return f"REASON_{exchange.upper()}_{asset.upper()}_{symbol.upper()}_{ts_clean}_{hash_prefix}"

@dataclass
class HypothesisObject:
    title: str
    supporting_evidence_count: int
    raw_support_pct: float
    derived_confidence: float
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ConfidenceBreakdown:
    evidence_strength: float
    sample_reliability: float
    data_completeness: float
    contradiction_penalty: float
    final_derived_confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ReasoningChain:
    reasoning_id: str
    primary_situation: str
    symbol: str
    exchange: str
    timestamp: str
    competing_hypotheses: Dict[str, Dict[str, Any]]
    confidence_breakdown: Dict[str, Any]
    minority_evidence_preserved: List[str]
    unknowns: List[str]
    overall_assessment: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
