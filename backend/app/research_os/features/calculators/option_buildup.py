from typing import Dict, Any, List
import pyarrow as pa
from app.research_os.features.calculators.base import BaseFeatureCalculator


class OptionBuildupCalculator(BaseFeatureCalculator):
    """Computes Open Interest Buildup signal (Long Buildup, Short Buildup, Covering, Unwinding)."""

    @property
    def feature_name(self) -> str:
        return "option_buildup"

    @property
    def output_fields(self) -> List[pa.Field]:
        return [
            pa.field("oi_change_ce", pa.int64()),
            pa.field("oi_change_pe", pa.int64()),
            pa.field("buildup_signal", pa.string()),
        ]

    def compute(self, snapshot_dict: Dict[str, Any], historical_context: Dict[str, Any]) -> Dict[str, Any]:
        ce_oi = snapshot_dict.get("ce_oi", 0)
        pe_oi = snapshot_dict.get("pe_oi", 0)
        ce_close = snapshot_dict.get("ce_close", 0.0)

        prev_ce_oi = historical_context.get("prev_ce_oi", 0)
        prev_pe_oi = historical_context.get("prev_pe_oi", 0)

        oi_chg_ce = ce_oi - prev_ce_oi if prev_ce_oi > 0 else 0
        oi_chg_pe = pe_oi - prev_pe_oi if prev_pe_oi > 0 else 0

        if oi_chg_ce > 0 and ce_close > 0:
            buildup = "LONG_BUILDUP"
        elif oi_chg_ce < 0 and ce_close > 0:
            buildup = "SHORT_COVERING"
        elif oi_chg_ce > 0 and ce_close < 0:
            buildup = "SHORT_BUILDUP"
        elif oi_chg_ce < 0 and ce_close < 0:
            buildup = "LONG_UNWINDING"
        else:
            buildup = "NEUTRAL"

        return {
            "oi_change_ce": oi_chg_ce,
            "oi_change_pe": oi_chg_pe,
            "buildup_signal": buildup,
        }
