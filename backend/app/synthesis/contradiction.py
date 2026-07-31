"""
Sprint AD — Contradiction & Failure Cluster Analyzer
Isolates contradicting historical memories, clusters failure modes,
and extracts common breakdown triggers.
"""

from typing import List, Dict, Any
from collections import Counter

class ContradictionAnalyzer:
    """
    Analyzes historical memory episodes that failed to resolve in expected direction.
    Isolates common breakdown triggers (e.g. Low Volume, PCR collapse, IV compression).
    """

    def analyze_contradictions(
        self,
        contradicting_memories: List[Dict[str, Any]],
        expected_direction: str
    ) -> Dict[str, Any]:
        """
        Returns structured contradiction analysis summary.
        """
        count = len(contradicting_memories)
        if count == 0:
            return {
                "contradicting_memories_count": 0,
                "largest_failure_cluster": "NONE",
                "failure_frequency": "0/0",
                "common_trigger": "No historical contradicting failure episodes found in top sample."
            }

        clusters = Counter()
        for mem in contradicting_memories:
            feats = mem.get("features", {})
            pcr = feats.get("pcr_oi", 1.0)
            vol_pillar = feats.get("volatility", "STABLE")
            flow = feats.get("participation", "MODERATE_RETAIL")

            if flow == "THIN_FLOW":
                clusters["LOW_INSTITUTIONAL_VOLUME"] += 1
            elif pcr < 0.85:
                clusters["PCR_COLLAPSE_BELOW_THRESHOLD"] += 1
            elif vol_pillar == "COMPRESSING":
                clusters["VOLATILITY_COMPRESSION_STALL"] += 1
            else:
                clusters["ORDER_BOOK_VACUUM_REVERSAL"] += 1

        top_cluster, top_count = clusters.most_common(1)[0]

        trigger_descriptions = {
            "LOW_INSTITUTIONAL_VOLUME": "Breakout stalled due to thin institutional volume participation.",
            "PCR_COLLAPSE_BELOW_THRESHOLD": "Put-Call Ratio collapsed below 0.85 critical support threshold.",
            "VOLATILITY_COMPRESSION_STALL": "Implied Volatility compression caused rangebound dissipation.",
            "ORDER_BOOK_VACUUM_REVERSAL": "Sudden liquidity vacuum displacement triggered sharp counter-reversal."
        }

        common_trigger = trigger_descriptions.get(top_cluster, "Counter-trend order book displacement.")

        return {
            "contradicting_memories_count": count,
            "largest_failure_cluster": top_cluster,
            "failure_frequency": f"{top_count}/{count}",
            "common_trigger": common_trigger
        }
