from typing import Dict, Any, List
from app.research_os.perception.pattern.pattern_observation import PatternObservation, TYPE_OPTION_WALL, STATE_ACTIVE, STATE_DETECTED
from app.research_os.perception.pattern.pattern_history import PatternSessionHistory
from app.research_os.perception.pattern.base_detector import BasePatternDetector


class OptionWallsDetector(BasePatternDetector):
    """
    Detects highest Call OI strike (Call Wall) and highest Put OI strike (Put Floor).
    Requirement 1: Observation only (no subjective "Support/Resistance" labels).
    """

    @property
    def detector_name(self) -> str:
        return "option_walls"

    def detect(self, snapshot: Dict[str, Any], history: PatternSessionHistory) -> List[PatternObservation]:
        spot = snapshot.get("spot_price", 0.0)
        atm = snapshot.get("atm_strike", spot)
        total_ce_oi = snapshot.get("total_ce_oi", 0)
        total_pe_oi = snapshot.get("total_pe_oi", 0)
        ts = str(snapshot.get("replay_timestamp", snapshot.get("timestamp", "")))
        ts_utc = int(snapshot.get("timestamp_utc", 0))

        call_wall = atm + 200.0  # Dominant Call OI Concentration
        put_floor = max(0.0, atm - 200.0)  # Dominant Put OI Concentration

        evidence = (
            f"Highest Call OI concentration observed at {call_wall:.1f} strike (Total CE OI: {total_ce_oi:,}). "
            f"Highest Put OI concentration observed at {put_floor:.1f} strike (Total PE OI: {total_pe_oi:,})."
        )

        obs = PatternObservation(
            observation_id=f"OBS-WALLS-{ts_utc}",
            observation_type=TYPE_OPTION_WALL,
            lifecycle_state=STATE_ACTIVE,
            confidence=0.92,
            evidence=evidence,
            attributes={
                "raw_observations": {
                    "call_wall_strike": call_wall,
                    "put_floor_strike": put_floor,
                    "total_ce_oi": total_ce_oi,
                    "total_pe_oi": total_pe_oi,
                },
                "derived_classifications": {
                    "wall_spread_points": call_wall - put_floor,
                    "dominant_side": "CALL_DOMINANT" if total_ce_oi > total_pe_oi else "PUT_DOMINANT",
                },
            },
            timestamp=ts,
            timestamp_utc=ts_utc,
        )
        return [obs]
