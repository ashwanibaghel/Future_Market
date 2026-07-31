import os
import json
import logging
import tempfile
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from app.research_os.governance.dataset_registry import RESEARCH_STORAGE_DIR, ensure_research_storage_structure

logger = logging.getLogger("research_os.replay.registry")

REPLAY_REGISTRY_DIR = os.path.join(RESEARCH_STORAGE_DIR, "replay_sessions")


class ReplayRegistry:
    """
    Requirement 7 Replay Session Registry & Checkpoint Manager.
    Persists replay session state manifests (`session_manifest.json`) using atomic file swaps.
    Enables atomic failure recovery without duplicating or skipping snapshots.
    """

    def __init__(self, base_dir: str = REPLAY_REGISTRY_DIR):
        ensure_research_storage_structure()
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        self.manifest_json = os.path.join(self.base_dir, "session_manifest.json")

    def save_checkpoint(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Saves or updates a replay session checkpoint atomically."""
        session_id = session_data["session_id"]
        entry = {
            "session_id": session_id,
            "symbol": str(session_data["symbol"]).upper(),
            "feature_version": str(session_data["feature_version"]),
            "replay_version": str(session_data.get("replay_version", "R-v1.0.0")),
            "current_index": int(session_data.get("current_index", 0)),
            "current_timestamp": session_data.get("current_timestamp"),
            "total_snapshots": int(session_data.get("total_snapshots", 0)),
            "status": str(session_data.get("status", "CREATED")),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "config": session_data.get("config", {}),
        }

        existing = self.list_sessions()
        filtered = [s for s in existing if s["session_id"] != session_id]
        filtered.append(entry)

        self._write_manifest_atomic(filtered)
        logger.debug("Checkpoint saved for session '%s' (Index: %d, Status: %s)", session_id, entry["current_index"], entry["status"])
        return entry

    def get_checkpoint(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves checkpoint data for a specific session ID."""
        sessions = self.list_sessions()
        for s in sessions:
            if s["session_id"] == session_id:
                return s
        return None

    def list_sessions(self) -> List[Dict[str, Any]]:
        """Lists all registered replay sessions."""
        if not os.path.exists(self.manifest_json):
            return []
        try:
            with open(self.manifest_json, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Failed reading replay session manifest: %s", str(exc))
            return []

    def _write_manifest_atomic(self, entries: List[Dict[str, Any]]):
        temp_dir = os.path.dirname(self.manifest_json)
        tf = tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8")
        json.dump(entries, tf, indent=2)
        tf.flush()
        tf.close()
        temp_name = tf.name
        try:
            os.replace(temp_name, self.manifest_json)
        except PermissionError:
            with open(self.manifest_json, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2)
            try:
                os.remove(temp_name)
            except Exception:
                pass
