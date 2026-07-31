from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from app.research_os.strategy.strategy_manifest import StrategyManifest
from app.research_os.strategy.strategy_context import StrategyContext
from app.research_os.strategy.decision_event import DecisionEvent


class BaseStrategyPlugin(ABC):
    """
    Requirement 1 & 8 Abstract Base Strategy Plugin Interface.
    Compatible with rule-based strategies, ML models, and LLM reasoning engines.
    Guarantees runtime state isolation and standardized lifecycle.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        # Requirement 2: Isolated runtime state per strategy instance
        self.state: Dict[str, Any] = {}

    @property
    @abstractmethod
    def manifest(self) -> StrategyManifest:
        """Exposes immutable StrategyManifest metadata."""
        pass

    def initialize(self, config: Optional[Dict[str, Any]] = None):
        """Called once when strategy is instantiated or configured."""
        if config:
            self.config.update(config)

    def on_session_start(self, session_meta: Dict[str, Any]):
        """Called at replay session start. Resets instance state for 100% determinism."""
        self.state.clear()

    @abstractmethod
    def on_snapshot(self, context: StrategyContext) -> Optional[DecisionEvent]:
        """
        Main signal evaluation method called per snapshot tick.
        Must return an immutable DecisionEvent or None.
        """
        pass

    def on_session_end(self, session_meta: Dict[str, Any]):
        """Called at replay session completion."""
        pass

    def shutdown(self):
        """Clean up strategy resources."""
        self.state.clear()
