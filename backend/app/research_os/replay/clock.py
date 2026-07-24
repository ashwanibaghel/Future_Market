import logging
from datetime import datetime
from typing import List, Optional
from app.research_os.replay.exceptions import TemporalLeakageError

logger = logging.getLogger("research_os.replay.clock")


class ReplayClock:
    """
    Chronological Replay Clock managing the current simulation tick timestamp.
    """

    def __init__(self, timestamps: List[datetime]):
        if not timestamps:
            raise ValueError("ReplayClock requires a non-empty list of sorted timestamps.")
        
        # Ensure timestamps are strictly sorted ascending
        self._timestamps: List[datetime] = sorted(list(set(timestamps)))
        self._current_index: int = 0

    @property
    def current_time(self) -> datetime:
        """Returns the current simulation tick timestamp."""
        return self._timestamps[self._current_index]

    @property
    def current_index(self) -> int:
        """Returns the current 0-based step index."""
        return self._current_index

    @property
    def total_steps(self) -> int:
        """Returns total number of timestamps in the replay timeline."""
        return len(self._timestamps)

    def advance(self) -> datetime:
        """Advances the clock by 1 minute step."""
        if self._current_index < len(self._timestamps) - 1:
            self._current_index += 1
            logger.debug("ReplayClock advanced to %s (step %d/%d)", self.current_time, self._current_index + 1, self.total_steps)
        else:
            logger.debug("ReplayClock reached end of timeline (%s)", self.current_time)
        return self.current_time

    def rewind(self) -> datetime:
        """Rewinds the clock by 1 minute step."""
        if self._current_index > 0:
            self._current_index -= 1
            logger.debug("ReplayClock rewound to %s (step %d/%d)", self.current_time, self._current_index + 1, self.total_steps)
        return self.current_time

    def seek(self, target_time: datetime) -> datetime:
        """Seeks the clock to a specific timestamp in the timeline."""
        if target_time not in self._timestamps:
            # Find closest previous timestamp if exact match not present
            valid_past = [t for t in self._timestamps if t <= target_time]
            if not valid_past:
                raise TemporalLeakageError(target_time, self._timestamps[0], f"Target time {target_time} precedes initial replay timeline.")
            target_time = valid_past[-1]

        self._current_index = self._timestamps.index(target_time)
        logger.info("ReplayClock seeked to %s", self.current_time)
        return self.current_time

    def reset(self) -> datetime:
        """Resets the clock back to the initial timestamp."""
        self._current_index = 0
        logger.info("ReplayClock reset to initial timestamp %s", self.current_time)
        return self.current_time

    def is_finished(self) -> bool:
        """Returns True if clock has reached the final timestamp."""
        return self._current_index >= len(self._timestamps) - 1
