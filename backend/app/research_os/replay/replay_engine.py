import logging
from typing import Dict, Any, List, Optional
from app.research_os.feature_store.feature_store import FeatureStore
from app.research_os.replay.replay_config import ReplayConfig
from app.research_os.replay.replay_session import ReplaySession
from app.research_os.replay.replay_registry import ReplayRegistry

logger = logging.getLogger("research_os.replay.engine")


class HistoricalReplayEngine:
    """
    Historical Replay Engine Orchestrator.
    Factory for creating, retrieving, and resuming ReplaySessions.
    Strictly replays data without containing trading or strategy logic (Requirement 6).
    """

    def __init__(
        self,
        feature_store: Optional[FeatureStore] = None,
        registry: Optional[ReplayRegistry] = None,
    ):
        self.store = feature_store or FeatureStore()
        self.registry = registry or ReplayRegistry()
        self.active_sessions: Dict[str, ReplaySession] = {}

    def create_session(self, session_id: str, config: ReplayConfig) -> ReplaySession:
        """Creates a new stateful ReplaySession."""
        session = ReplaySession(
            session_id=session_id,
            config=config,
            feature_store=self.store,
            registry=self.registry,
        )
        self.active_sessions[session_id] = session
        logger.info("Created ReplaySession '%s' for symbol %s (%d total snapshots)", session_id, config.symbol, session.cursor.total_snapshots)
        return session

    def get_session(self, session_id: str) -> Optional[ReplaySession]:
        """Retrieves active session by ID."""
        return self.active_sessions.get(session_id)

    def resume_session(self, session_id: str) -> Optional[ReplaySession]:
        """Requirement 7: Resumes a session from latest checkpoint manifest."""
        checkpoint = self.registry.get_checkpoint(session_id)
        if not checkpoint:
            logger.warning("No checkpoint found for session ID '%s'", session_id)
            return None

        config_dict = checkpoint.get("config", {})
        config = ReplayConfig.from_dict(config_dict)

        session = self.create_session(session_id, config)
        resumed = session.resume_from_checkpoint()
        if resumed:
            logger.info("Successfully resumed session '%s' from checkpoint index %d", session_id, session.cursor.current_index)
            return session
        return None
