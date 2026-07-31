import logging
from typing import Dict, Any, List, Optional
from app.research_os.perception.regime.regime_observation import RegimeObservation, STATE_REGIME_TRANSITION

logger = logging.getLogger("research_os.perception.regime.history")


class RegimeSessionHistory:
    """
    Requirement 3 Regime Session History Tracker.
    Tracks current regime, previous regime, duration in ticks, stability evolution, and transition count.
    Feeds future Memory & Similarity Engines.
    """

    def __init__(self):
        self._history: List[RegimeObservation] = []
        self.current_regime: Optional[str] = None
        self.previous_regime: Optional[str] = None
        self.duration_ticks: int = 0
        self.transition_count: int = 0

    def add_observation(self, observation: RegimeObservation):
        """Appends regime observation and updates trajectory state."""
        self._history.append(observation)

        if observation.regime_dimension == "TREND_STRENGTH":
            new_regime = observation.state_label
            if self.current_regime is None:
                self.current_regime = new_regime
                self.duration_ticks = 1
            elif new_regime != self.current_regime:
                self.previous_regime = self.current_regime
                self.current_regime = new_regime
                self.duration_ticks = 1
                self.transition_count += 1
            else:
                self.duration_ticks += 1

    def get_history(self, limit: Optional[int] = None) -> List[RegimeObservation]:
        if limit:
            return self._history[-limit:]
        return self._history

    def clear(self):
        self._history.clear()
        self.current_regime = None
        self.previous_regime = None
        self.duration_ticks = 0
        self.transition_count = 0
