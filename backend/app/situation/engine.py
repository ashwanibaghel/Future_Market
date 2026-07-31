"""
Sprint AA — Market Situation Understanding Engine v1
Temporal Situation Understanding & Evolution Engine.

📜 THE CONSTITUTION LINE (NON-NEGOTIABLE RULE):
"The Situation Engine shall never directly infer trading decisions.
Its only responsibility is to answer: 'What is happening in the market right now?' NOT 'What should I do?'"
"""

from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timezone

from app.situation.taxonomy import (
    EvolutionPhase,
    TrendPillar,
    VolatilityPillar,
    ParticipationPillar,
    StructurePillar,
    MarketContext,
    Situation,
    SITUATION_TAXONOMY
)
from app.situation.graph import ObservationGraph

class SituationEngine:
    """
    Temporal Situation Understanding Engine.
    Processes observation timelines across consecutive snapshots to infer
    explainable, evolving market situations.
    """

    def __init__(self):
        self.graph_builder = ObservationGraph()
        self.active_situation_history: Dict[str, Dict[str, Any]] = {}

    def understand(
        self,
        snapshot: Dict[str, Any],
        observations: List[Dict[str, Any]],
        recent_window_observations: Optional[List[List[Dict[str, Any]]]] = None
    ) -> List[Situation]:
        """
        Converts snapshot observations and sliding window timeline into Situation objects.
        """
        if not observations:
            return []

        ts_iso = str(snapshot.get("timestamp", ""))
        graph_summary = self.graph_builder.build_and_collapse(observations)
        nodes = set(graph_summary["active_nodes"])
        evidence = graph_summary["evidence_pool"]

        situations: List[Situation] = []

        # ── SITUATION 1: ACCUMULATION BEHAVIOUR ──────────────────────────────
        if ("OBS_PUT_WRITING_AGGRESSIVE" in nodes or "OBS_PCR_EXPANSION" in nodes) and (
            "OBS_ATM_UPSHIFT" in nodes or "OBS_LONG_BUILDUP" in nodes
        ):
            why = []
            unknowns = []
            if "OBS_PUT_WRITING_AGGRESSIVE" in nodes:
                why.append("Persistent Put Writing detected indicating strong institutional floor support.")
            if "OBS_ATM_UPSHIFT" in nodes:
                why.append("ATM strike migrated higher following upward spot momentum.")
            if "OBS_PCR_EXPANSION" in nodes:
                why.append(f"Put-Call Ratio (PCR) expanded to {evidence.get('pcr_oi', 1.25):.2f}.")

            if "OBS_IV_EXPANSION" not in nodes:
                unknowns.append("Volatility expansion confirmation unavailable.")
            if "OBS_CALL_WALL_BREACH" not in nodes:
                unknowns.append("Call Wall breach unconfirmed.")

            reasoning = "Concurrent Put Writing, ATM Upshift, and PCR expansion indicate sustained institutional accumulation behavior."

            situations.append(self._create_or_update_situation(
                sit_id="SIT_ACCUMULATION_BEHAVIOUR",
                snapshot_ts=ts_iso,
                nodes=nodes,
                why=why,
                reasoning=reasoning,
                unknowns=unknowns,
                evidence=evidence,
                trend=TrendPillar.UPWARD_DRIFT,
                volatility=VolatilityPillar.STABLE,
                participation=ParticipationPillar.HIGH_INSTITUTIONAL,
                structure=StructurePillar.ACCULATION,
                recent_window=recent_window_observations
            ))

        # ── SITUATION 2: DISTRIBUTION BEHAVIOUR ────────────────────────────
        elif ("OBS_CALL_WRITING_AGGRESSIVE" in nodes or "OBS_PCR_CONTRACTION" in nodes) and (
            "OBS_ATM_DOWNSHIFT" in nodes or "OBS_SHORT_BUILDUP" in nodes
        ):
            why = []
            unknowns = []
            if "OBS_CALL_WRITING_AGGRESSIVE" in nodes:
                why.append("Persistent Call Writing detected indicating strong overhead resistance.")
            if "OBS_ATM_DOWNSHIFT" in nodes:
                why.append("ATM strike migrated lower following downward spot momentum.")
            if "OBS_PCR_CONTRACTION" in nodes:
                why.append(f"Put-Call Ratio (PCR) contracted to {evidence.get('pcr_oi', 0.75):.2f}.")

            if "OBS_PUT_FLOOR_BREACH" not in nodes:
                unknowns.append("Put Floor breach unconfirmed.")

            reasoning = "Concurrent Call Writing, ATM Downshift, and PCR contraction indicate sustained institutional distribution behavior."

            situations.append(self._create_or_update_situation(
                sit_id="SIT_DISTRIBUTION_BEHAVIOUR",
                snapshot_ts=ts_iso,
                nodes=nodes,
                why=why,
                reasoning=reasoning,
                unknowns=unknowns,
                evidence=evidence,
                trend=TrendPillar.DOWNWARD_PRESSURE,
                volatility=VolatilityPillar.STABLE,
                participation=ParticipationPillar.HIGH_INSTITUTIONAL,
                structure=StructurePillar.DISTRIBUTION,
                recent_window=recent_window_observations
            ))

        # ── SITUATION 3: LEVEL BREACH EXPANSION ─────────────────────────────
        elif "OBS_CALL_WALL_BREACH" in nodes or "OBS_PUT_FLOOR_BREACH" in nodes:
            why = []
            unknowns = []
            if "OBS_CALL_WALL_BREACH" in nodes:
                why.append(f"Spot price breached major Call Wall strike at {evidence.get('call_wall_strike', 0):.1f}.")
            if "OBS_PUT_FLOOR_BREACH" in nodes:
                why.append(f"Spot price breached major Put Floor strike at {evidence.get('put_floor_strike', 0):.1f}.")

            if "OBS_IV_EXPANSION" not in nodes:
                unknowns.append("Implied Volatility surge confirmation inconclusive.")

            reasoning = "Spot price actively breached key boundary walls/floors, indicating range expansion and potential trend continuation."

            situations.append(self._create_or_update_situation(
                sit_id="SIT_LEVEL_BREACH_EXPANSION",
                snapshot_ts=ts_iso,
                nodes=nodes,
                why=why,
                reasoning=reasoning,
                unknowns=unknowns,
                evidence=evidence,
                trend=TrendPillar.UPWARD_DRIFT if "OBS_CALL_WALL_BREACH" in nodes else TrendPillar.DOWNWARD_PRESSURE,
                volatility=VolatilityPillar.EXPANDING,
                participation=ParticipationPillar.HIGH_INSTITUTIONAL,
                structure=StructurePillar.EXPANSION_BREAKOUT,
                recent_window=recent_window_observations
            ))

        # ── SITUATION 4: SHORT COVERING MOMENTUM ─────────────────────────────
        elif "OBS_SHORT_COVERING" in nodes:
            why = [
                "Short Covering detected: Spot rising while Call Open Interest unwinds rapidly.",
                f"Call OI unwound by {evidence.get('call_oi_unwinding_pct', 0.0):.2f}%."
            ]
            unknowns = ["New buyer volume confirmation unavailable."]
            reasoning = "Unwinding short positions are driving rapid upward spot displacement."

            situations.append(self._create_or_update_situation(
                sit_id="SIT_SHORT_COVERING_MOMENTUM",
                snapshot_ts=ts_iso,
                nodes=nodes,
                why=why,
                reasoning=reasoning,
                unknowns=unknowns,
                evidence=evidence,
                trend=TrendPillar.UPWARD_DRIFT,
                volatility=VolatilityPillar.EXPANDING,
                participation=ParticipationPillar.MODERATE_RETAIL,
                structure=StructurePillar.TRENDING,
                recent_window=recent_window_observations
            ))

        # ── SITUATION 5: LONG LIQUIDATION PRESSURE ───────────────────────────
        elif "OBS_LONG_UNWINDING" in nodes:
            why = [
                "Long Liquidation detected: Spot falling while Put Open Interest unwinds rapidly.",
                f"Put OI unwound by {evidence.get('put_oi_unwinding_pct', 0.0):.2f}%."
            ]
            unknowns = ["Fresh short seller volume confirmation unavailable."]
            reasoning = "Unwinding long positions are driving rapid downward spot decline."

            situations.append(self._create_or_update_situation(
                sit_id="SIT_LONG_LIQUIDATION_PRESSURE",
                snapshot_ts=ts_iso,
                nodes=nodes,
                why=why,
                reasoning=reasoning,
                unknowns=unknowns,
                evidence=evidence,
                trend=TrendPillar.DOWNWARD_PRESSURE,
                volatility=VolatilityPillar.EXPANDING,
                participation=ParticipationPillar.MODERATE_RETAIL,
                structure=StructurePillar.TRENDING,
                recent_window=recent_window_observations
            ))

        # ── DEFAULT FALLBACK: CONSOLIDATION COMPRESSION ──────────────────────
        if not situations:
            why = ["Price structure compressing within balanced order flow boundaries."]
            unknowns = ["Directional breakout trigger unconfirmed."]
            reasoning = "Order flow is balanced between call and put participants, maintaining a rangebound compression state."

            situations.append(self._create_or_update_situation(
                sit_id="SIT_CONSOLIDATION_COMPRESSION",
                snapshot_ts=ts_iso,
                nodes=nodes,
                why=why,
                reasoning=reasoning,
                unknowns=unknowns,
                evidence=evidence,
                trend=TrendPillar.SIDEWAYS_FLAT,
                volatility=VolatilityPillar.COMPRESSING,
                participation=ParticipationPillar.THIN_FLOW,
                structure=StructurePillar.RANGE_COMPRESSION,
                recent_window=recent_window_observations
            ))

        return situations

    def _create_or_update_situation(
        self,
        sit_id: str,
        snapshot_ts: str,
        nodes: Set[str],
        why: List[str],
        reasoning: str,
        unknowns: List[str],
        evidence: Dict[str, Any],
        trend: TrendPillar,
        volatility: VolatilityPillar,
        participation: ParticipationPillar,
        structure: StructurePillar,
        recent_window: Optional[List[List[Dict[str, Any]]]] = None
    ) -> Situation:
        """
        Calculates multi-factor confidence, tracks temporal evolution phases, and generates timeline data.
        """
        obs_agreement = min(1.0, len(nodes) / 3.0)
        evidence_strength = 0.85 if evidence else 0.70
        temporal_stability = 0.90 if recent_window and len(recent_window) >= 2 else 0.75
        baseline_score = 0.80

        confidence = round(
            (0.35 * obs_agreement) +
            (0.25 * evidence_strength) +
            (0.25 * temporal_stability) +
            (0.15 * baseline_score), 4
        )

        hist = self.active_situation_history.get(sit_id)
        if not hist:
            phase = EvolutionPhase.BUILDING
            start_time = snapshot_ts
            duration = 1
            self.active_situation_history[sit_id] = {
                "start_time": snapshot_ts,
                "duration": 1,
                "peak_time": snapshot_ts,
                "peak_conf": confidence
            }
        else:
            duration = hist["duration"] + 1
            start_time = hist["start_time"]
            hist["duration"] = duration
            if confidence > hist["peak_conf"]:
                hist["peak_conf"] = confidence
                hist["peak_time"] = snapshot_ts

            if duration <= 2:
                phase = EvolutionPhase.BUILDING
            elif duration <= 5:
                phase = EvolutionPhase.SUSTAINED
            elif duration <= 10:
                phase = EvolutionPhase.ACCELERATING
            else:
                phase = EvolutionPhase.WEAKENING

        peak_time = self.active_situation_history[sit_id]["peak_time"]
        severity_lvl = 4 if sit_id in ("SIT_LEVEL_BREACH_EXPANSION", "SIT_LIQUIDITY_VACUUM_DISPLACEMENT") else 3

        context = MarketContext(
            trend=trend,
            volatility=volatility,
            participation=participation,
            structure=structure
        )

        return Situation(
            situation_id=sit_id,
            evolution_phase=phase,
            confidence=confidence,
            severity=f"LEVEL_{severity_lvl}_HIGH",
            severity_level=severity_lvl,
            start_time=start_time,
            peak_time=peak_time,
            latest_time=snapshot_ts,
            duration_minutes=duration,
            why=why,
            reasoning=reasoning,
            unknowns=unknowns,
            supporting_observations=sorted(list(nodes)),
            market_context=context.to_dict(),
            evidence=evidence
        )
