from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass(frozen=True)
class StrategyManifest:
    """
    Requirement 1 Immutable Strategy Manifest Metadata.
    Allows automatic discovery, compatibility validation, and future strategy marketplace support.
    """
    strategy_name: str
    strategy_version: str
    author: str
    description: str
    supported_symbols: List[str]
    required_features: List[str]
    minimum_feature_version: str = "F-v1.0.0"
    parameters: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "author": self.author,
            "description": self.description,
            "supported_symbols": self.supported_symbols,
            "required_features": self.required_features,
            "minimum_feature_version": self.minimum_feature_version,
            "parameters": self.parameters,
            "tags": self.tags,
        }
