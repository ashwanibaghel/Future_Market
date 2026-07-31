from typing import Dict, Any, List
import pyarrow as pa
from app.research_os.features.calculators.base import BaseFeatureCalculator


class SpotVWAPCalculator(BaseFeatureCalculator):
    """Computes Volume Weighted Average Price (VWAP)."""

    @property
    def feature_name(self) -> str:
        return "spot_vwap"

    @property
    def output_fields(self) -> List[pa.Field]:
        return [
            pa.field("vwap", pa.float64()),
        ]

    def compute(self, snapshot_dict: Dict[str, Any], historical_context: Dict[str, Any]) -> Dict[str, Any]:
        spot = snapshot_dict.get("spot", 0.0)
        tot_vol = snapshot_dict.get("ce_vol", 0) + snapshot_dict.get("pe_vol", 0)

        cum_vol = historical_context.get("cum_vol", 0) + tot_vol
        cum_pv = historical_context.get("cum_pv", 0.0) + (spot * tot_vol)

        historical_context["cum_vol"] = cum_vol
        historical_context["cum_pv"] = cum_pv

        vwap = round(cum_pv / max(1, cum_vol), 2)
        return {"vwap": vwap}
