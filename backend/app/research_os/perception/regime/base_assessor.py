from abc import ABC, abstractmethod
from typing import Dict, Any, List
from app.research_os.perception.pattern.pattern_observation import PatternObservation
from app.research_os.perception.regime.regime_feature import RegimeFeature
from app.research_os.perception.regime.regime_history import RegimeSessionHistory


class BaseRegimeAssessor(ABC):
    """
    Requirement 1 Abstract Regime Assessor Interface.
    Every regime assessor implements this interface independently to produce RegimeFeature objects.
    """

    @property
    @abstractmethod
    def assessor_name(self) -> str:
        """Name of the assessor / analyzer plugin."""
        pass

    @abstractmethod
    def assess(
        self,
        snapshot: Dict[str, Any],
        pattern_observations: List[PatternObservation],
        history: RegimeSessionHistory,
    ) -> List[RegimeFeature]:
        """
        Assesses observed market conditions and returns Stage 1 RegimeFeature objects.
        """
        pass
