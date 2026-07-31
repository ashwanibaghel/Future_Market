from dataclasses import dataclass
from typing import Dict, Any
from app.research_os.perception.perception_frame import PerceptionFrame


@dataclass(frozen=True)
class PerceptionEvent:
    """Standardized event emitted whenever a PerceptionFrame is synthesized."""
    event_id: str
    session_id: str
    frame: PerceptionFrame

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "session_id": self.session_id,
            "frame": self.frame.to_dict(),
        }
