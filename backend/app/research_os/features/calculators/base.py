from abc import ABC, abstractmethod
from typing import Dict, Any, List
import pyarrow as pa


class BaseFeatureCalculator(ABC):
    """
    Abstract plugin interface for modular quantitative feature calculators.
    Every feature calculation (PCR, IV Skew, VWAP, Max Pain, ML Embeddings) implements this interface.
    """

    @property
    @abstractmethod
    def feature_name(self) -> str:
        """Name identifier of the feature calculator."""
        pass

    @property
    @abstractmethod
    def output_fields(self) -> List[pa.Field]:
        """PyArrow fields contributed by this feature calculator."""
        pass

    @abstractmethod
    def compute(self, snapshot_dict: Dict[str, Any], historical_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Computes feature values for a single snapshot state.
        Returns a dict of feature values matching output_fields.
        """
        pass
