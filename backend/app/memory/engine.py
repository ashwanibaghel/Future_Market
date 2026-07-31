"""
Sprint AB — Market Memory Formation Engine v1
Main Orchestrator converting Situation Timelines into persistent, immutable Episodic Memories.

📜 THE CONSTITUTION LINE (ARTICLE IX - MEMORY IMMUTABILITY):
"Once a Market Memory Episode is created, its observed facts shall never be modified or rewritten.
Corrections, reinterpretations, or reflections must create new metadata objects, never rewrite history."
"""

from typing import List, Dict, Any, Optional

from app.memory.taxonomy import (
    generate_memory_id,
    EpisodicMemory
)
from app.memory.segmenter import EpisodeSegmenter
from app.memory.outcome import OutcomeEngine

class MemoryEngine:
    """
    Main Market Memory Formation Engine.
    Converts situation timelines into locked, immutable EpisodicMemory records
    grounded strictly in 6-horizon physical outcomes (Memory + Outcome).
    """

    def __init__(self):
        self.segmenter = EpisodeSegmenter()
        self.outcome_engine = OutcomeEngine()

    def process_partition_situations(
        self,
        snapshot_situation_pairs: List[tuple]
    ) -> List[EpisodicMemory]:
        """
        Processes an ordered list of (snapshot_meta, situations_list) tuples
        and produces completed, immutable EpisodicMemory objects.
        """
        raw_episodes = []
        all_snapshots = []

        for snap, sits in snapshot_situation_pairs:
            all_snapshots.append(snap)
            completed = self.segmenter.process_snapshot_situations(snap, sits)
            raw_episodes.extend(completed)

        if all_snapshots:
            flushed = self.segmenter.flush_remaining(all_snapshots[-1].get("timestamp", ""))
            raw_episodes.extend(flushed)

        memories: List[EpisodicMemory] = []
        num_snaps = len(all_snapshots)

        for ep in raw_episodes:
            ep_snaps = ep.get("snapshots", [])
            if not ep_snaps:
                continue

            last_ep_ts = ep_snaps[-1].get("timestamp", "")
            subsequent_snaps = [s for s in all_snapshots if s.get("timestamp", "") > last_ep_ts]

            # 1. Compute 6-horizon physical outcomes
            outcomes = self.outcome_engine.calculate_multi_horizon_outcomes(ep, subsequent_snaps)

            # 2. Extract dynamic extensible feature signature map
            m_ctx = ep.get("market_context", {})
            evidence = ep.get("evidence", {})
            features = {
                "trend": m_ctx.get("trend", "SIDEWAYS_FLAT"),
                "volatility": m_ctx.get("volatility", "STABLE"),
                "participation": m_ctx.get("participation", "MODERATE_RETAIL"),
                "structure": m_ctx.get("structure", "RANGE_COMPRESSION"),
                "pcr_oi": float(evidence.get("pcr_oi", 1.0)),
                "atm_shift": int(evidence.get("atm_shift", 0)),
                "severity_level": int(ep_snaps[-1].get("severity_level", 3)) if ep_snaps else 3
            }

            # 3. Collision-Proof Memory ID
            start_ts = ep.get("start_time", "")
            mem_id = generate_memory_id(
                exchange=ep.get("exchange", "NSE"),
                asset="INDEX",
                symbol=ep.get("symbol", "NIFTY"),
                start_iso=start_ts
            )

            sit_id = ep.get("situation_id", "")

            memories.append(EpisodicMemory(
                memory_id=mem_id,
                memory_type="EPISODIC_MEMORY",
                primary_situation=sit_id,
                symbol=ep.get("symbol", "NIFTY"),
                exchange=ep.get("exchange", "NSE"),
                start_time=start_ts,
                end_time=ep.get("end_time", ""),
                duration_minutes=int(ep.get("duration_minutes", 1)),
                peak_confidence=float(ep.get("peak_confidence", 0.80)),
                key_reasoning=str(ep.get("reasoning", "")),
                unknowns=list(ep.get("unknowns", [])),
                features=features,
                episode_outcomes=outcomes,
                reflection={}  # Reserved for Sprint AD Experience Generalization Engine
            ))

        return memories
