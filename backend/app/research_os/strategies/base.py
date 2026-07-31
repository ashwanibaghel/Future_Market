from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseStrategyPlugin(ABC):
    """
    Abstract Strategy Plugin interface.
    Consumes snapshot events from Replay Engine and produces prediction decision dicts.
    """

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """Name of the strategy plugin."""
        pass

    @property
    @abstractmethod
    def strategy_version(self) -> str:
        """Version of the strategy algorithm."""
        pass

    @abstractmethod
    def evaluate_snapshot(self, snapshot: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Evaluates current snapshot event and returns decision prediction dict or None.
        Must read only features present in snapshot.
        """
        pass
