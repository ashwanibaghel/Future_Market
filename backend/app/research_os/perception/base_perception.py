from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class BasePerceptionModule(ABC):
    """
    Requirement 1, 2, & 3 Abstract Perception Module Interface.
    Observes market state and produces explainable perception outputs.
    MUST NEVER emit trade signals (BUY/SELL/EXIT).
    """

    @property
    @abstractmethod
    def module_name(self) -> str:
        """Unique identifier name of the perception module."""
        pass

    @property
    @abstractmethod
    def module_version(self) -> str:
        """Version string of the perception algorithm."""
        pass

    @property
    def required_features(self) -> List[str]:
        """List of required feature names in the input snapshot."""
        return []

    @property
    def dependencies(self) -> List[str]:
        """Requirement 3: List of prerequisite perception module names required before execution."""
        return []

    def initialize(self, config: Optional[Dict[str, Any]] = None):
        """Lifecycle initialization method."""
        pass

    @abstractmethod
    def process_snapshot(self, snapshot: Dict[str, Any], prior_perceptions: Dict[str, Any]) -> Dict[str, Any]:
        """
        Requirement 2 Explainable Observation Generator.
        Must return a dict containing:
        - 'confidence': float (0.0 .. 1.0)
        - 'evidence': str (human-readable explanation string)
        - 'metadata': dict (structured perceived observations)
        """
        pass
