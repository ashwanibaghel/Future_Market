import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

logger = logging.getLogger("acquisition.validator")


def calculate_intraday_time_gaps(timestamps: List[datetime]) -> int:
    """Calculates missing 1-minute gaps within trading session hours (09:15 to 15:30 IST)."""
    if len(timestamps) <= 1:
        return 0

    sorted_ts = sorted(timestamps)
    gaps = 0
    for i in range(1, len(sorted_ts)):
        t1 = sorted_ts[i - 1]
        t2 = sorted_ts[i]

        if t1.date() == t2.date():
            diff = int((t2 - t1).total_seconds() / 60.0)
            if diff > 1:
                gaps += (diff - 1)
    return gaps


class DataQualityAuditor:
    """Audits candle dataset completeness, market minute gaps, and duplicate timestamps."""

    @staticmethod
    def audit_candles(instrument_key: str, candles: List[List[Any]]) -> Dict[str, Any]:
        """Performs structured quality audit on candle array."""
        total_rows = len(candles)
        if total_rows == 0:
            return {
                "quality_pass": False,
                "instrument_key": instrument_key,
                "total_rows": 0,
                "missing_minutes_count": 0,
                "duplicate_count": 0,
                "status": "FAIL_EMPTY",
            }

        duplicate_count = 0
        seen_ts = set()
        dt_list = []

        for c in candles:
            ts_str = c[0]
            if ts_str in seen_ts:
                duplicate_count += 1
            else:
                seen_ts.add(ts_str)

            try:
                dt_list.append(datetime.fromisoformat(ts_str))
            except Exception:
                pass

        missing_minutes = calculate_intraday_time_gaps(dt_list)
        quality_pass = (duplicate_count == 0 and total_rows > 0)

        return {
            "quality_pass": quality_pass,
            "instrument_key": instrument_key,
            "total_rows": total_rows,
            "duplicate_count": duplicate_count,
            "missing_minutes_count": missing_minutes,
            "start_time": candles[0][0] if candles else "",
            "end_time": candles[-1][0] if candles else "",
            "status": "PASS" if quality_pass else "FAIL",
        }
