from typing import Dict, Any, List
from app.research_os.perception.pattern.pattern_observation import PatternObservation, TYPE_STRIKE_CLUSTER, STATE_ACTIVE
from app.research_os.perception.pattern.pattern_history import PatternSessionHistory
from app.research_os.perception.pattern.base_detector import BasePatternDetector


class StrikeClusterDetector(BasePatternDetector):
    """Detects liquidity strike density around ATM strike."""

    @property
    def detector_name(self) -> str:
        return "strike_cluster"

    def detect(self, snapshot: Dict[str, Any], history: PatternSessionHistory) -> List[PatternObservation]:
        spot = snapshot.get("spot_price", 0.0)
        atm = snapshot.get("atm_strike", spot)
        total_ce = snapshot.get("total_ce_oi", 0)
        total_pe = snapshot.get("total_pe_oi", 0)
        ts = str(snapshot.get("replay_timestamp", snapshot.get("timestamp", "")))
        ts_utc = int(snapshot.get("timestamp_utc", 0))

        tot_oi = total_ce + total_pe
        density = "HIGH" if tot_oi > 10000 else "NORMAL"

        evidence = f"Liquidity concentration density around ATM ({atm:.1f}) classified as {density} (Total OI: {tot_oi:,})."

        obs = PatternObservation(
            observation_id=f"OBS-CLUSTER-{ts_utc}",
            observation_type=TYPE_STRIKE_CLUSTER,
            lifecycle_state=STATE_ACTIVE,
            confidence=0.88,
            evidence=evidence,
            attributes={
                "raw_observations": {
                    "atm_strike": atm,
                    "total_combined_oi": tot_oi,
                },
                "derived_classifications": {
                    "cluster_density": density,
                },
            },
            timestamp=ts,
            timestamp_utc=ts_utc,
        )
        return [obs]
