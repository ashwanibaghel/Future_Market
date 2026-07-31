"""
Sprint AD — Memory Importance Evaluator
Calculates memory importance weights (0.5 to 2.5) for retrieved historical episodes
based on severity level, regime rarity, and duration.
"""

from typing import Dict, Any

class MemoryImportanceEvaluator:
    """
    Evaluates historical memory importance weights to compute
    Importance-Weighted Success Rates.
    """

    @staticmethod
    def calculate_importance_weight(memory: Dict[str, Any]) -> float:
        """
        Returns a normalized importance weight multiplier (0.5 to 2.5).
        """
        weight = 1.0

        feats = memory.get("features", {})
        sev_lvl = feats.get("severity_level", 3)
        dur = memory.get("duration_minutes", 1)
        sit_id = memory.get("primary_situation", "")

        # 1. High Severity Breach Bonus
        if sev_lvl >= 4:
            weight += 0.4

        # 2. Rare Situation / Liquidity Vacuum Bonus
        if sit_id in ("SIT_LIQUIDITY_VACUUM_DISPLACEMENT", "SIT_LEVEL_BREACH_EXPANSION"):
            weight += 0.3
        elif sit_id == "SIT_EXPIRY_PINNING_CLUSTER":
            weight += 0.2

        # 3. Episode Duration Weighting
        if dur >= 15:
            weight += 0.3
        elif dur >= 5:
            weight += 0.1

        return round(weight, 2)
