from abc import ABC, abstractmethod
from typing import Dict, Any, List
from app.research_os.perception.pattern.pattern_observation import PatternObservation
from app.research_os.perception.regime.regime_observation import RegimeObservation


class BaseSituationSynthesizer(ABC):
    """
    Abstract Situation Synthesizer Interface.
    Synthesizes pattern and regime observations into cohesive situation assessment properties.
    """

    @property
    @abstractmethod
    def synthesizer_name(self) -> str:
        pass

    @abstractmethod
    def synthesize(
        self,
        snapshot: Dict[str, Any],
        pattern_observations: List[PatternObservation],
        regime_observations: List[RegimeObservation],
    ) -> Dict[str, Any]:
        pass
