from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass
class RegimeFeature:
    """
    Requirement 2 Stage 1 Regime Feature.
    Represents measurable regime characteristics before state synthesis.
    """
    feature_id: str
    feature_name: str
    value: float
    confidence: float
    supporting_pattern_ids: List[str] = field(default_factory=list)
    timestamp_utc: int = 0
