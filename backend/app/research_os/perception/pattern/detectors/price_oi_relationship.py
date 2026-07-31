from typing import Dict, Any, List
from app.research_os.perception.pattern.pattern_observation import PatternObservation, TYPE_PRICE_OI_RELATION, STATE_ACTIVE
from app.research_os.perception.pattern.pattern_history import PatternSessionHistory
from app.research_os.perception.pattern.base_detector import BasePatternDetector


class PriceOIRelationshipDetector(BasePatternDetector):
    """
    Requirement 1 & 2 Price vs OI Delta Relationship Detector.
    Clearly separates raw observations (Spot price, Call/Put OI changes)
    from derived buildup classifications (LONG_BUILDUP, SHORT_COVERING, etc.).
    """

    @property
    def detector_name(self) -> str:
        return "price_oi_relationship"

    def detect(self, snapshot: Dict[str, Any], history: PatternSessionHistory) -> List[PatternObservation]:
        spot = snapshot.get("spot_price", 0.0)
        oi_chg_ce = snapshot.get("oi_change_ce", 0)
        oi_chg_pe = snapshot.get("oi_change_pe", 0)
        buildup_signal = snapshot.get("buildup_signal", "NEUTRAL")
        ts = str(snapshot.get("replay_timestamp", snapshot.get("timestamp", "")))
        ts_utc = int(snapshot.get("timestamp_utc", 0))

        evidence = (
            f"Spot Price observed at {spot:.2f}; Call OI change: {oi_chg_ce:+,d}; Put OI change: {oi_chg_pe:+,d}. "
            f"Derived relationship classification: {buildup_signal}."
        )

        obs = PatternObservation(
            observation_id=f"OBS-PRICEOI-{ts_utc}",
            observation_type=TYPE_PRICE_OI_RELATION,
            lifecycle_state=STATE_ACTIVE,
            confidence=0.91,
            evidence=evidence,
            attributes={
                "raw_observations": {
                    "spot_price": spot,
                    "oi_change_ce": oi_chg_ce,
                    "oi_change_pe": oi_chg_pe,
                },
                "derived_classifications": {
                    "buildup_signal": buildup_signal,
                    "is_divergence_trap": (oi_chg_ce < 0 and buildup_signal == "SHORT_COVERING"),
                },
            },
            timestamp=ts,
            timestamp_utc=ts_utc,
        )
        return [obs]
