"""
Sprint AF — Decision Support Engine v1
Taxonomy, Decision Support Schema, and Full Immutable Audit Package.

📜 THE CONSTITUTION LINE (ARTICLE I & VIII):
"Zero buy/sell action signals. AI explains & assesses execution readiness; human decides."
"""

import hashlib
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

def generate_assessment_id(exchange: str, asset: str, symbol: str, start_iso: str) -> str:
    """
    Generates a globally unique Assessment ID:
    DS_{EXCHANGE}_{ASSET}_{SYMBOL}_{YYYYMMDDTHHMMSS}_{HASH6}
    """
    ts_clean = start_iso.replace("-", "").replace(":", "").replace(".000Z", "").replace("Z", "")
    raw_key = f"DS_{exchange}_{asset}_{symbol}_{start_iso}".encode("utf-8")
    hash_prefix = hashlib.sha256(raw_key).hexdigest()[:6].upper()
    return f"DS_{exchange.upper()}_{asset.upper()}_{symbol.upper()}_{ts_clean}_{hash_prefix}"

@dataclass
class InformationGap:
    missing_information: List[str]
    gap_impact: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class DecisionSupportAssessment:
    assessment_id: str
    primary_situation: str
    symbol: str
    exchange: str
    timestamp: str
    dominant_hypothesis: str
    evidence_quality_confidence: float
    key_supporting_evidence: List[str]
    key_risks: List[str]
    information_gap: Dict[str, Any]
    recommended_monitoring: List[str]
    execution_readiness: str
    traceability: Dict[str, Any]
    audit_package: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
