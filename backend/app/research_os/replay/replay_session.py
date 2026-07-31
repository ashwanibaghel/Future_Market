import time
import logging
from typing import Dict, Any, List, Optional, Callable, Generator, Union
import pyarrow as pa

from app.research_os.feature_store.feature_store import FeatureStore
from app.research_os.replay.replay_config import ReplayConfig
from app.research_os.replay.replay_cursor import ReplayCursor, ReplayStats
from app.research_os.replay.replay_registry import ReplayRegistry
from app.research_os.replay.replay_version import DEFAULT_REPLAY_VERSION

logger = logging.getLogger("research_os.replay.session")


class ReplaySession:
    """
    Replay Session Manager.
    Implements Deterministic Time Navigation API (play, pause, step, seek),
    Enriched Replay Event Emission, Multi-Strategy Listener Broadcasting,
    and Atomic Session Checkpointing.
    """

    def __init__(
        self,
        session_id: str,
        config: ReplayConfig,
        feature_store: Optional[FeatureStore] = None,
        registry: Optional[ReplayRegistry] = None,
    ):
        self.session_id = session_id
        self.config = config
        self.store = feature_store or FeatureStore()
        self.registry = registry or ReplayRegistry()

        self.status = "CREATED"
        self.listeners: List[Callable[[Dict[str, Any]], None]] = []

        # Load Feature Datasets based on Config
        self.feature_table: Optional[pa.Table] = self._load_session_feature_table()
        total_rows = self.feature_table.num_rows if self.feature_table is not None else 0
        self.cursor = ReplayCursor(total_snapshots=total_rows)

        # Convert PyArrow Table to column-oriented dictionary for sub-millisecond playback
        self._p_dict = self.feature_table.to_pydict() if self.feature_table is not None else {}

    def _load_session_feature_table(self) -> Optional[pa.Table]:
        """Loads feature datasets across requested date range from FeatureStore."""
        start_yr = int(self.config.start_date.split("-")[0])
        end_yr = int(self.config.end_date.split("-")[0])

        tables = []
        for yr in range(start_yr, end_yr + 1):
            # Scan months
            for m in range(1, 13):
                m_str = f"{yr}-{m:02d}"
                if m_str < self.config.start_date[:7] or m_str > self.config.end_date[:7]:
                    continue
                if self.store.has_features(self.config.symbol, yr, m, self.config.feature_version):
                    tbl = self.store.get_features(self.config.symbol, yr, m, self.config.feature_version)
                    if tbl is not None and tbl.num_rows > 0:
                        tables.append(tbl)

        if not tables:
            logger.warning("No FeatureStore datasets found for %s (%s to %s)", self.config.symbol, self.config.start_date, self.config.end_date)
            return None

        # Concatenate PyArrow tables deterministically
        return pa.concat_tables(tables)

    def register_listener(self, listener: Callable[[Dict[str, Any]], None]):
        """Requirement 5: Registers strategy or event bus listener."""
        if listener not in self.listeners:
            self.listeners.append(listener)

    def _construct_enriched_event(self, idx: int) -> Dict[str, Any]:
        """Requirement 3: Constructs enriched snapshot event."""
        event = {
            "session_id": self.session_id,
            "replay_timestamp": self._p_dict["timestamp"][idx],
            "snapshot_index": idx,
            "feature_version": self.config.feature_version,
            "replay_version": self.config.replay_version,
        }
        # Add all feature columns
        for k in self._p_dict.keys():
            if k not in event:
                event[k] = self._p_dict[k][idx]
        return event

    def step(self, count: int = 1) -> List[Dict[str, Any]]:
        """
        Advances cursor by count ticks and dispatches enriched events to all registered listeners.
        """
        if self.feature_table is None or self.cursor.current_index >= self.cursor.total_snapshots:
            self.status = "COMPLETED"
            self._checkpoint()
            return []

        self.cursor.start_timer()
        events = []

        for _ in range(count):
            if self.cursor.current_index >= self.cursor.total_snapshots:
                self.status = "COMPLETED"
                break

            idx = self.cursor.current_index
            event = self._construct_enriched_event(idx)
            ts = event["replay_timestamp"]
            self.cursor.advance(ts)

            # Broadcast to multi-strategy listeners
            for listener in self.listeners:
                try:
                    listener(event)
                except Exception as exc:
                    logger.error("Listener execution failed: %s", str(exc))

            events.append(event)

            if self.config.replay_speed > 0.0:
                time.sleep(self.config.replay_speed)

        if self.cursor.current_index % 500 == 0 or self.status in ("COMPLETED", "PAUSED"):
            self._checkpoint()
        return events

    def play(self) -> Generator[Dict[str, Any], None, None]:
        """
        Plays continuous replay until EOF, pause, or error.
        Yields enriched snapshot events sequentially.
        """
        self.status = "RUNNING"
        self.cursor.start_timer()

        while self.status == "RUNNING" and self.cursor.current_index < self.cursor.total_snapshots:
            step_events = self.step(count=1)
            if not step_events:
                break
            yield step_events[0]

        if self.cursor.current_index >= self.cursor.total_snapshots:
            self.status = "COMPLETED"
        self._checkpoint()

    def pause(self):
        """Halts replay playback at current cursor."""
        self.status = "PAUSED"
        self._checkpoint()
        logger.info("Replay Session '%s' PAUSED at index %d", self.session_id, self.cursor.current_index)

    def seek(self, target_timestamp: str) -> bool:
        """Seeks replay cursor to exact timestamp within dataset."""
        if "timestamp" not in self._p_dict:
            return False

        timestamps = self._p_dict["timestamp"]
        for idx, ts in enumerate(timestamps):
            if ts >= target_timestamp:
                self.cursor.seek_to(idx, ts)
                self._checkpoint()
                logger.info("Replay Session '%s' SEEKED to index %d (%s)", self.session_id, idx, ts)
                return True
        return False

    def resume_from_checkpoint(self) -> bool:
        """Requirement 7: Resumes session state from latest checkpoint manifest."""
        checkpoint = self.registry.get_checkpoint(self.session_id)
        if not checkpoint:
            return False

        saved_index = checkpoint.get("current_index", 0)
        saved_timestamp = checkpoint.get("current_timestamp")

        if saved_index < self.cursor.total_snapshots:
            self.cursor.seek_to(saved_index, saved_timestamp)
            self.status = checkpoint.get("status", "PAUSED")
            logger.info("Resumed Session '%s' from checkpoint index %d", self.session_id, saved_index)
            return True
        return False

    def get_stats(self) -> ReplayStats:
        """Requirement 4: Returns session execution telemetry."""
        return self.cursor.get_stats(
            session_id=self.session_id,
            symbol=self.config.symbol,
            feature_version=self.config.feature_version,
            replay_version=self.config.replay_version,
            status=self.status,
        )

    def _checkpoint(self):
        """Saves atomic session state to registry."""
        session_data = {
            "session_id": self.session_id,
            "symbol": self.config.symbol,
            "feature_version": self.config.feature_version,
            "replay_version": self.config.replay_version,
            "current_index": self.cursor.current_index,
            "current_timestamp": self.cursor.current_timestamp,
            "total_snapshots": self.cursor.total_snapshots,
            "status": self.status,
            "config": self.config.to_dict(),
        }
        self.registry.save_checkpoint(session_data)
