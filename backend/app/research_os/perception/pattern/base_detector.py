from abc import ABC, abstractmethod
from typing import Dict, Any, List
from app.research_os.perception.pattern.pattern_observation import PatternObservation
from app.research_os.perception.pattern.pattern_history import PatternSessionHistory


class BasePatternDetector(ABC):
    """
    Requirement 6 Abstract Pattern Detector Interface.
    Every pattern detector implements this interface independently.
    """

    @property
    @abstractmethod
    def detector_name(self) -> str:
        """Name of the sub-detector."""
        pass

    @abstractmethod
    def detect(self, snapshot: Dict[str, Any], history: PatternSessionHistory) -> List[PatternObservation]:
        """
        Detects structural pattern observations from snapshot and session history.
        Must return a list of PatternObservation objects.
        """
        pass
