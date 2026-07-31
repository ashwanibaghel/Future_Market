from typing import Dict, Any, List
from app.research_os.perception.pattern.pattern_observation import PatternObservation, TYPE_OI_MOVEMENT, STATE_ACTIVE
from app.research_os.perception.pattern.pattern_history import PatternSessionHistory
from app.research_os.perception.pattern.base_detector import BasePatternDetector


class OIMovementDetector(BasePatternDetector):
    """Measures raw Call/Put Open Interest changes."""

    @property
    def detector_name(self) -> str:
        return "oi_movement"

    def detect(self, snapshot: Dict[str, Any], history: PatternSessionHistory) -> List[PatternObservation]:
        oi_chg_ce = snapshot.get("oi_change_ce", 0)
        oi_chg_pe = snapshot.get("oi_change_pe", 0)
        ts = str(snapshot.get("replay_timestamp", snapshot.get("timestamp", "")))
        ts_utc = int(snapshot.get("timestamp_utc", 0))

        evidence = f"Call OI net change: {oi_chg_ce:+,d}; Put OI net change: {oi_chg_pe:+,d} over current snapshot tick."

        obs = PatternObservation(
            observation_id=f"OBS-OIMOVE-{ts_utc}",
            observation_type=TYPE_OI_MOVEMENT,
            lifecycle_state=STATE_ACTIVE,
            confidence=0.95,
            evidence=evidence,
            attributes={
                "raw_observations": {
                    "oi_change_ce": oi_chg_ce,
                    "oi_change_pe": oi_chg_pe,
                },
                "derived_classifications": {
                    "net_oi_flow": "NET_CALL_EXPANSION" if oi_chg_ce > oi_chg_pe else "NET_PUT_EXPANSION",
                },
            },
            timestamp=ts,
            timestamp_utc=ts_utc,
        )
        return [obs]
