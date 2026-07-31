from typing import Dict, Any, List
import pyarrow as pa
from app.research_os.features.calculators.base import BaseFeatureCalculator


class OptionPCRCalculator(BaseFeatureCalculator):
    """Computes Volume PCR and Open Interest PCR."""

    @property
    def feature_name(self) -> str:
        return "option_pcr"

    @property
    def output_fields(self) -> List[pa.Field]:
        return [
            pa.field("pcr_volume", pa.float64()),
            pa.field("pcr_oi", pa.float64()),
        ]

    def compute(self, snapshot_dict: Dict[str, Any], historical_context: Dict[str, Any]) -> Dict[str, Any]:
        ce_vol = snapshot_dict.get("ce_vol", 0)
        pe_vol = snapshot_dict.get("pe_vol", 0)
        ce_oi = snapshot_dict.get("ce_oi", 0)
        pe_oi = snapshot_dict.get("pe_oi", 0)

        pcr_vol = round(pe_vol / max(1, ce_vol), 4)
        pcr_oi = round(pe_oi / max(1, ce_oi), 4)

        return {
            "pcr_volume": pcr_vol,
            "pcr_oi": pcr_oi,
        }
