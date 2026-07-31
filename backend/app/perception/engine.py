"""
Sprint Z — Artificial Market Perception Engine v1
Rule-Based Explainable Observation Engine.

Converts raw snapshot, canonical strikes, and feature records into structured, 100% explainable
Observation objects with explicit quantitative evidence metrics. Zero predictions or trade signals.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.perception.taxonomy import (
    ObservationCategory,
    SeverityLevel,
    SEVERITY_NUMERIC_MAP,
    Observation,
    OBSERVATION_TAXONOMY
)

class ObservationEngine:
    """
    Deterministic Market Perception Engine.
    Evaluates historical replay snapshots against quantitative rules to produce
    explainable market observation objects.
    """

    def observe(
        self,
        snapshot: Dict[str, Any],
        strikes: List[Dict[str, Any]],
        features: Dict[str, Any],
        prev_snapshot: Optional[Dict[str, Any]] = None,
        prev_features: Optional[Dict[str, Any]] = None
    ) -> List[Observation]:
        """
        Generates structured observations for a single market snapshot.
        """
        observations: List[Observation] = []

        spot = snapshot.get("spot_price", 0.0)
        atm_strike = snapshot.get("atm_strike", 0.0)
        symbol = snapshot.get("symbol", "NIFTY")
        expiry = snapshot.get("expiry", "")

        pcr_vol = features.get("pcr_volume", 1.0)
        pcr_oi = features.get("pcr_oi", 1.0)
        call_wall = features.get("call_wall_strike", atm_strike)
        put_floor = features.get("put_floor_strike", atm_strike)
        tot_call_oi = features.get("tot_call_oi", 0)
        tot_put_oi = features.get("tot_put_oi", 0)
        tot_call_vol = features.get("tot_call_volume", 0)
        tot_put_vol = features.get("tot_put_volume", 0)

        prev_spot = prev_snapshot.get("spot_price", spot) if prev_snapshot else spot
        prev_atm = prev_snapshot.get("atm_strike", atm_strike) if prev_snapshot else atm_strike
        prev_pcr_oi = prev_features.get("pcr_oi", pcr_oi) if prev_features else pcr_oi
        prev_tot_call_oi = prev_features.get("tot_call_oi", tot_call_oi) if prev_features else tot_call_oi
        prev_tot_put_oi = prev_features.get("tot_put_oi", tot_put_oi) if prev_features else tot_put_oi

        spot_change_pct = round(((spot - prev_spot) / prev_spot) * 100.0, 4) if prev_spot > 0 else 0.0
        call_oi_change_pct = round(((tot_call_oi - prev_tot_call_oi) / prev_tot_call_oi) * 100.0, 4) if prev_tot_call_oi > 0 else 0.0
        put_oi_change_pct = round(((tot_put_oi - prev_tot_put_oi) / prev_tot_put_oi) * 100.0, 4) if prev_tot_put_oi > 0 else 0.0

        # ── RULE 1: AGGRESSIVE PUT WRITING ──────────────────────────────────
        if pcr_oi >= 1.25 and put_oi_change_pct > 2.0:
            severity = SeverityLevel.LEVEL_4_CRITICAL if put_oi_change_pct > 10.0 else SeverityLevel.LEVEL_3_HIGH
            observations.append(Observation(
                observation_id="OBS_PUT_WRITING_AGGRESSIVE",
                category=ObservationCategory.OPEN_INTEREST,
                confidence=min(0.98, 0.70 + (pcr_oi * 0.15)),
                severity=severity,
                severity_numeric=SEVERITY_NUMERIC_MAP[severity],
                description=OBSERVATION_TAXONOMY["OBS_PUT_WRITING_AGGRESSIVE"]["description"],
                evidence={
                    "pcr_oi": pcr_oi,
                    "put_oi_change_pct": put_oi_change_pct,
                    "tot_put_oi": tot_put_oi,
                    "spot_change_pct": spot_change_pct,
                    "put_floor_strike": put_floor
                }
            ))

        # ── RULE 2: AGGRESSIVE CALL WRITING ──────────────────────────────────
        if pcr_oi <= 0.75 and call_oi_change_pct > 2.0:
            severity = SeverityLevel.LEVEL_4_CRITICAL if call_oi_change_pct > 10.0 else SeverityLevel.LEVEL_3_HIGH
            observations.append(Observation(
                observation_id="OBS_CALL_WRITING_AGGRESSIVE",
                category=ObservationCategory.OPEN_INTEREST,
                confidence=min(0.98, 0.70 + ((1.0 / max(0.1, pcr_oi)) * 0.10)),
                severity=severity,
                severity_numeric=SEVERITY_NUMERIC_MAP[severity],
                description=OBSERVATION_TAXONOMY["OBS_CALL_WRITING_AGGRESSIVE"]["description"],
                evidence={
                    "pcr_oi": pcr_oi,
                    "call_oi_change_pct": call_oi_change_pct,
                    "tot_call_oi": tot_call_oi,
                    "spot_change_pct": spot_change_pct,
                    "call_wall_strike": call_wall
                }
            ))

        # ── RULE 3: LONG BUILDUP ────────────────────────────────────────────
        if spot_change_pct > 0.05 and (put_oi_change_pct > 1.0 or call_oi_change_pct > 1.0):
            severity = SeverityLevel.LEVEL_3_HIGH if spot_change_pct > 0.3 else SeverityLevel.LEVEL_2_MODERATE
            observations.append(Observation(
                observation_id="OBS_LONG_BUILDUP",
                category=ObservationCategory.OPEN_INTEREST,
                confidence=0.85,
                severity=severity,
                severity_numeric=SEVERITY_NUMERIC_MAP[severity],
                description=OBSERVATION_TAXONOMY["OBS_LONG_BUILDUP"]["description"],
                evidence={
                    "spot_change_pct": spot_change_pct,
                    "put_oi_change_pct": put_oi_change_pct,
                    "call_oi_change_pct": call_oi_change_pct,
                    "pcr_volume": pcr_vol
                }
            ))

        # ── RULE 4: SHORT BUILDUP ────────────────────────────────────────────
        if spot_change_pct < -0.05 and (call_oi_change_pct > 1.0 or put_oi_change_pct > 1.0):
            severity = SeverityLevel.LEVEL_3_HIGH if spot_change_pct < -0.3 else SeverityLevel.LEVEL_2_MODERATE
            observations.append(Observation(
                observation_id="OBS_SHORT_BUILDUP",
                category=ObservationCategory.OPEN_INTEREST,
                confidence=0.85,
                severity=severity,
                severity_numeric=SEVERITY_NUMERIC_MAP[severity],
                description=OBSERVATION_TAXONOMY["OBS_SHORT_BUILDUP"]["description"],
                evidence={
                    "spot_change_pct": spot_change_pct,
                    "call_oi_change_pct": call_oi_change_pct,
                    "put_oi_change_pct": put_oi_change_pct,
                    "pcr_volume": pcr_vol
                }
            ))

        # ── RULE 5: SHORT COVERING ──────────────────────────────────────────
        if spot_change_pct > 0.05 and call_oi_change_pct < -1.0:
            severity = SeverityLevel.LEVEL_4_CRITICAL if spot_change_pct > 0.4 else SeverityLevel.LEVEL_3_HIGH
            observations.append(Observation(
                observation_id="OBS_SHORT_COVERING",
                category=ObservationCategory.OPEN_INTEREST,
                confidence=0.90,
                severity=severity,
                severity_numeric=SEVERITY_NUMERIC_MAP[severity],
                description=OBSERVATION_TAXONOMY["OBS_SHORT_COVERING"]["description"],
                evidence={
                    "spot_change_pct": spot_change_pct,
                    "call_oi_unwinding_pct": call_oi_change_pct,
                    "call_wall_strike": call_wall
                }
            ))

        # ── RULE 6: LONG UNWINDING ──────────────────────────────────────────
        if spot_change_pct < -0.05 and put_oi_change_pct < -1.0:
            severity = SeverityLevel.LEVEL_4_CRITICAL if spot_change_pct < -0.4 else SeverityLevel.LEVEL_3_HIGH
            observations.append(Observation(
                observation_id="OBS_LONG_UNWINDING",
                category=ObservationCategory.OPEN_INTEREST,
                confidence=0.90,
                severity=severity,
                severity_numeric=SEVERITY_NUMERIC_MAP[severity],
                description=OBSERVATION_TAXONOMY["OBS_LONG_UNWINDING"]["description"],
                evidence={
                    "spot_change_pct": spot_change_pct,
                    "put_oi_unwinding_pct": put_oi_change_pct,
                    "put_floor_strike": put_floor
                }
            ))

        # ── RULE 7: PCR EXPANSION / CONTRACTION ──────────────────────────────
        pcr_delta = round(pcr_oi - prev_pcr_oi, 4)
        if pcr_delta >= 0.05:
            observations.append(Observation(
                observation_id="OBS_PCR_EXPANSION",
                category=ObservationCategory.VOLUME,
                confidence=0.88,
                severity=SeverityLevel.LEVEL_2_MODERATE,
                severity_numeric=SEVERITY_NUMERIC_MAP[SeverityLevel.LEVEL_2_MODERATE],
                description=OBSERVATION_TAXONOMY["OBS_PCR_EXPANSION"]["description"],
                evidence={
                    "pcr_oi": pcr_oi,
                    "prev_pcr_oi": prev_pcr_oi,
                    "pcr_delta": pcr_delta
                }
            ))
        elif pcr_delta <= -0.05:
            observations.append(Observation(
                observation_id="OBS_PCR_CONTRACTION",
                category=ObservationCategory.VOLUME,
                confidence=0.88,
                severity=SeverityLevel.LEVEL_2_MODERATE,
                severity_numeric=SEVERITY_NUMERIC_MAP[SeverityLevel.LEVEL_2_MODERATE],
                description=OBSERVATION_TAXONOMY["OBS_PCR_CONTRACTION"]["description"],
                evidence={
                    "pcr_oi": pcr_oi,
                    "prev_pcr_oi": prev_pcr_oi,
                    "pcr_delta": pcr_delta
                }
            ))

        # ── RULE 8: CALL WALL / PUT FLOOR BREACH ─────────────────────────────
        if spot > call_wall > 0:
            severity = SeverityLevel.LEVEL_5_EXTREME if (spot - call_wall) / call_wall > 0.01 else SeverityLevel.LEVEL_4_CRITICAL
            observations.append(Observation(
                observation_id="OBS_CALL_WALL_BREACH",
                category=ObservationCategory.KEY_LEVELS,
                confidence=0.95,
                severity=severity,
                severity_numeric=SEVERITY_NUMERIC_MAP[severity],
                description=OBSERVATION_TAXONOMY["OBS_CALL_WALL_BREACH"]["description"],
                evidence={
                    "spot_price": spot,
                    "call_wall_strike": call_wall,
                    "breach_amount": round(spot - call_wall, 2)
                }
            ))
        elif 0 < spot < put_floor:
            severity = SeverityLevel.LEVEL_5_EXTREME if (put_floor - spot) / put_floor > 0.01 else SeverityLevel.LEVEL_4_CRITICAL
            observations.append(Observation(
                observation_id="OBS_PUT_FLOOR_BREACH",
                category=ObservationCategory.KEY_LEVELS,
                confidence=0.95,
                severity=severity,
                severity_numeric=SEVERITY_NUMERIC_MAP[severity],
                description=OBSERVATION_TAXONOMY["OBS_PUT_FLOOR_BREACH"]["description"],
                evidence={
                    "spot_price": spot,
                    "put_floor_strike": put_floor,
                    "breach_amount": round(put_floor - spot, 2)
                }
            ))

        # ── RULE 9: ATM SHIFT ────────────────────────────────────────────────
        if prev_atm > 0 and atm_strike != prev_atm:
            obs_id = "OBS_ATM_UPSHIFT" if atm_strike > prev_atm else "OBS_ATM_DOWNSHIFT"
            observations.append(Observation(
                observation_id=obs_id,
                category=ObservationCategory.ATM_SHIFT,
                confidence=1.0,
                severity=SeverityLevel.LEVEL_2_MODERATE,
                severity_numeric=SEVERITY_NUMERIC_MAP[SeverityLevel.LEVEL_2_MODERATE],
                description=OBSERVATION_TAXONOMY[obs_id]["description"],
                evidence={
                    "prev_atm_strike": prev_atm,
                    "new_atm_strike": atm_strike,
                    "spot_price": spot
                }
            ))

        # ── RULE 10: IV EXPANSION & CRUSH ────────────────────────────────────
        atm_strikes_data = [s for s in strikes if s.get("strike") == atm_strike]
        if atm_strikes_data:
            avg_iv = sum(s.get("iv", 0.0) for s in atm_strikes_data) / len(atm_strikes_data)
            if avg_iv > 35.0:
                observations.append(Observation(
                    observation_id="OBS_IV_EXPANSION",
                    category=ObservationCategory.VOLATILITY,
                    confidence=0.90,
                    severity=SeverityLevel.LEVEL_3_HIGH,
                    severity_numeric=SEVERITY_NUMERIC_MAP[SeverityLevel.LEVEL_3_HIGH],
                    description=OBSERVATION_TAXONOMY["OBS_IV_EXPANSION"]["description"],
                    evidence={
                        "atm_strike": atm_strike,
                        "atm_avg_iv": round(avg_iv, 2),
                        "iv_threshold": 35.0
                    }
                ))

        # ── FALLBACK DEFAULT OBSERVATION IF NO SPECIFIC RULE FIRED ───────────
        if not observations:
            observations.append(Observation(
                observation_id="OBS_STRUCTURE_STABLE",
                category=ObservationCategory.PRICE_STRUCTURE,
                confidence=0.75,
                severity=SeverityLevel.LEVEL_1_LOW,
                severity_numeric=SEVERITY_NUMERIC_MAP[SeverityLevel.LEVEL_1_LOW],
                description="Market structure stable with balanced order flow.",
                evidence={
                    "spot_price": spot,
                    "atm_strike": atm_strike,
                    "pcr_oi": pcr_oi,
                    "pcr_volume": pcr_vol
                }
            ))

        return observations
