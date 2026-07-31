from abc import ABC, abstractmethod
from typing import Dict, Any, List


class BaseMetricCalculator(ABC):
    """
    Requirement 4 Abstract Plugin Interface for Modular Evaluation Metrics.
    Allows new performance metrics to be added without altering the core evaluation engine.
    """

    @property
    @abstractmethod
    def metric_name(self) -> str:
        """Unique identifier of the metric calculator."""
        pass

    @abstractmethod
    def calculate(self, decisions: List[Dict[str, Any]], price_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculates specific performance metrics from decision events and price trajectory.
        Returns a dictionary of calculated metric values.
        """
        pass
