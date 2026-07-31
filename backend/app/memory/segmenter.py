"""
Sprint AB — State & Session-Driven Episode Segmenter
Groups continuous Situation State timelines into dynamic market episodes.

CRITICAL ARCHITECTURAL GUARANTEE (SESSION BOUNDARY DETECTOR):
Episodes ARE BOUNDED by market session closes (15:30 IST / >15 min gap between snapshots).
An episode NEVER spans overnight across non-trading hours or weekends.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

class SessionBoundaryDetector:
    """
    Detects market session closes and timestamp gaps > 15 minutes
    to prevent invalid overnight or weekend episode accumulation.
    """

    @staticmethod
    def is_session_boundary(last_iso: str, curr_iso: str) -> bool:
        if not last_iso or not curr_iso:
            return False

        try:
            # Format: 2026-07-01T03:45:00Z
            t_last = datetime.fromisoformat(last_iso.replace("Z", "+00:00"))
            t_curr = datetime.fromisoformat(curr_iso.replace("Z", "+00:00"))
            gap_seconds = (t_curr - t_last).total_seconds()
            
            # Gap > 15 minutes (900s) signifies market close, overnight gap, or weekend gap
            return gap_seconds > 900.0 or t_last.date() != t_curr.date()
        except Exception:
            return False

class EpisodeSegmenter:
    """
    Tracks state continuity of active market situations across consecutive snapshots.
    Emits completed raw episode objects when situation state terminates OR when session boundary is crossed.
    """

    def __init__(self):
        self.active_episodes: Dict[str, Dict[str, Any]] = {}
        self.last_snapshot_ts: str = ""

    def process_snapshot_situations(
        self,
        snapshot: Dict[str, Any],
        situations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Ingests snapshot situations and returns any completed raw episode objects.
        """
        completed_episodes = []
        current_sit_ids = {s["situation_id"] for s in situations}
        ts_iso = snapshot.get("timestamp", "")

        # Check session boundary
        session_ended = SessionBoundaryDetector.is_session_boundary(self.last_snapshot_ts, ts_iso)

        active_ids = list(self.active_episodes.keys())
        for sit_id in active_ids:
            if session_ended or sit_id not in current_sit_ids:
                # Situation ended OR Market Session Closed -> Close active episode
                ep = self.active_episodes.pop(sit_id)
                ep["end_time"] = self.last_snapshot_ts if session_ended else ts_iso
                ep["duration_minutes"] = max(1, len(ep["snapshots"]))
                completed_episodes.append(ep)

        # Add current snapshot to active episodes or start new ones
        for sit in situations:
            sit_id = sit["situation_id"]
            if sit_id not in self.active_episodes:
                self.active_episodes[sit_id] = {
                    "situation_id": sit_id,
                    "symbol": snapshot.get("symbol", "NIFTY"),
                    "exchange": snapshot.get("exchange", "NSE"),
                    "start_time": ts_iso,
                    "end_time": ts_iso,
                    "peak_confidence": sit.get("confidence", 0.0),
                    "reasoning": sit.get("reasoning", ""),
                    "unknowns": sit.get("unknowns", []),
                    "market_context": sit.get("market_context", {}),
                    "evidence": sit.get("evidence", {}),
                    "snapshots": [snapshot]
                }
            else:
                ep = self.active_episodes[sit_id]
                ep["snapshots"].append(snapshot)
                if sit.get("confidence", 0.0) > ep["peak_confidence"]:
                    ep["peak_confidence"] = sit.get("confidence", 0.0)

        self.last_snapshot_ts = ts_iso
        return completed_episodes

    def flush_remaining(self, last_ts: str) -> List[Dict[str, Any]]:
        """
        Flushes all remaining active episodes at end of partition.
        """
        completed = []
        for sit_id, ep in list(self.active_episodes.items()):
            ep["end_time"] = last_ts
            ep["duration_minutes"] = max(1, len(ep["snapshots"]))
            completed.append(ep)
        self.active_episodes.clear()
        return completed
