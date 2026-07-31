from typing import Dict, Any, List
from app.research_os.perception.pattern.pattern_observation import PatternObservation, TYPE_MAX_PAIN_SHIFT, STATE_ACTIVE, STATE_STRENGTHENING
from app.research_os.perception.pattern.pattern_history import PatternSessionHistory
from app.research_os.perception.pattern.base_detector import BasePatternDetector


class MaxPainDetector(BasePatternDetector):
    """Tracks Max Pain strike movement and writer drift."""

    @property
    def detector_name(self) -> str:
        return "max_pain"

    def detect(self, snapshot: Dict[str, Any], history: PatternSessionHistory) -> List[PatternObservation]:
        spot = snapshot.get("spot_price", 0.0)
        max_pain = snapshot.get("max_pain_strike", spot)
        ts = str(snapshot.get("replay_timestamp", snapshot.get("timestamp", "")))
        ts_utc = int(snapshot.get("timestamp_utc", 0))

        # Compare with previous active max pain observation in history
        prev_max_pain = spot
        active = history.get_active_patterns()
        for p in reversed(active):
            if p.observation_type == TYPE_MAX_PAIN_SHIFT:
                prev_max_pain = p.attributes.get("raw_observations", {}).get("max_pain_strike", spot)
                break

        shift = max_pain - prev_max_pain
        state = STATE_STRENGTHENING if shift != 0 else STATE_ACTIVE

        evidence = f"Max Pain strike observed at {max_pain:.1f} (Shift: {shift:+.1f} points from previous snapshot)."

        obs = PatternObservation(
            observation_id=f"OBS-MAXPAIN-{ts_utc}",
            observation_type=TYPE_MAX_PAIN_SHIFT,
            lifecycle_state=state,
            confidence=0.90,
            evidence=evidence,
            attributes={
                "raw_observations": {
                    "max_pain_strike": max_pain,
                    "previous_max_pain_strike": prev_max_pain,
                    "max_pain_shift_points": shift,
                },
                "derived_classifications": {
                    "writer_drift": "BULLISH_DRIFT" if shift > 0 else ("BEARISH_DRIFT" if shift < 0 else "STABLE"),
                },
            },
            timestamp=ts,
            timestamp_utc=ts_utc,
        )
        return [obs]
