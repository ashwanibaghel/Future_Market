import logging
from typing import Dict, Any, List, Optional
from app.research_os.perception.pattern.pattern_observation import PatternObservation, STATE_EXPIRED, STATE_ACTIVE

logger = logging.getLogger("research_os.perception.pattern.history")


class PatternSessionHistory:
    """
    Requirement 4 & 5 Pattern Lifecycle Tracker & Replay Session History.
    Maintains lightweight in-memory history of PatternObservation objects during replay.
    Feeds future Similarity Engine, Memory Engine, and Knowledge Graph.
    """

    def __init__(self):
        self._history: List[PatternObservation] = []
        self._active_patterns: Dict[str, PatternObservation] = {}

    def add_observation(self, observation: PatternObservation):
        """Appends observation to session history and updates active patterns."""
        self._history.append(observation)
        if observation.lifecycle_state != STATE_EXPIRED:
            self._active_patterns[observation.observation_id] = observation
        elif observation.observation_id in self._active_patterns:
            del self._active_patterns[observation.observation_id]

    def get_active_patterns(self) -> List[PatternObservation]:
        """Returns all currently active pattern observations."""
        return list(self._active_patterns.values())

    def get_history(self, limit: Optional[int] = None) -> List[PatternObservation]:
        """Returns session history of pattern observations."""
        if limit:
            return self._history[-limit:]
        return self._history

    def clear(self):
        """Clears session history at replay start."""
        self._history.clear()
        self._active_patterns.clear()
