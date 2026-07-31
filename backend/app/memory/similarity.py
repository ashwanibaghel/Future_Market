"""
Sprint AC — Decoupled Structural Similarity & Weight Policy Ranking Engine
Computes handcrafted explainable structural similarity match scores with Weighted Policy Support
(DEFAULT, TRENDING_DAY, EXPIRY_DAY) and human-readable why_retrieved match rationales.
"""

from typing import Dict, Any, List, Optional

# ── WEIGHT POLICY REGISTRY ──────────────────────────────────────────────────
WEIGHT_POLICIES = {
    "DEFAULT": {
        "trend": 0.25,
        "volatility": 0.20,
        "structure": 0.25,
        "severity": 0.15,
        "pcr": 0.15
    },
    "TRENDING_DAY": {
        "trend": 0.40,
        "structure": 0.25,
        "volatility": 0.15,
        "severity": 0.10,
        "pcr": 0.10
    },
    "EXPIRY_DAY": {
        "structure": 0.35,
        "pcr": 0.30,
        "severity": 0.15,
        "trend": 0.10,
        "volatility": 0.10
    }
}

class StructuralSimilarityEngine:
    """
    Independent Symbolic Similarity Matcher & Ranker with Weighted Policy Support.
    Compares 4-pillar context, severity level, PCR, and situation state parameters
    with explicit, human-readable match breakdowns and why_retrieved rationales.
    """

    def compute_similarity_with_policy(
        self,
        candidate_features: Dict[str, Any],
        historical_features: Dict[str, Any],
        policy_name: str = "DEFAULT"
    ) -> Dict[str, Any]:
        """
        Computes a normalized structural similarity score (0.0 to 1.0) using specified Weight Policy.
        """
        policy = WEIGHT_POLICIES.get(policy_name, WEIGHT_POLICIES["DEFAULT"])
        breakdown = {}
        why_retrieved = []
        score = 0.0

        # 1. Trend Pillar Match
        w_trend = policy["trend"]
        trend_match = candidate_features.get("trend") == historical_features.get("trend")
        breakdown["trend_match"] = "100%" if trend_match else "0%"
        if trend_match:
            score += w_trend
            why_retrieved.append(f"100% Trend Pillar Match ({candidate_features.get('trend')})")

        # 2. Volatility Pillar Match
        w_vol = policy["volatility"]
        vol_match = candidate_features.get("volatility") == historical_features.get("volatility")
        breakdown["volatility_match"] = "100%" if vol_match else "0%"
        if vol_match:
            score += w_vol
            why_retrieved.append(f"100% Volatility Pillar Match ({candidate_features.get('volatility')})")

        # 3. Structure Pillar Match
        w_struct = policy["structure"]
        struct_match = candidate_features.get("structure") == historical_features.get("structure")
        breakdown["structure_match"] = "100%" if struct_match else "0%"
        if struct_match:
            score += w_struct
            why_retrieved.append(f"100% Structure Pillar Match ({candidate_features.get('structure')})")

        # 4. Severity Level Proximity
        w_sev = policy["severity"]
        cand_sev = candidate_features.get("severity_level", 3)
        hist_sev = historical_features.get("severity_level", 3)
        sev_diff = abs(cand_sev - hist_sev)
        sev_ratio = max(0.0, 1.0 - (sev_diff * 0.33))
        score += (w_sev * sev_ratio)
        breakdown["severity_proximity"] = f"{int(sev_ratio * 100)}%"
        if sev_ratio >= 0.66:
            why_retrieved.append(f"Close Severity Level Proximity (Lvl {cand_sev} vs Lvl {hist_sev})")

        # 5. PCR Proximity Match
        w_pcr = policy["pcr"]
        cand_pcr = float(candidate_features.get("pcr_oi", 1.0))
        hist_pcr = float(historical_features.get("pcr_oi", 1.0))
        pcr_diff = abs(cand_pcr - hist_pcr)
        pcr_ratio = 1.0 if pcr_diff <= 0.15 else (0.5 if pcr_diff <= 0.35 else 0.0)
        score += (w_pcr * pcr_ratio)
        breakdown["pcr_proximity"] = f"{int(pcr_ratio * 100)}%"
        if pcr_ratio > 0.0:
            why_retrieved.append(f"Proximity PCR Match ({cand_pcr:.2f} vs {hist_pcr:.2f})")

        final_score = round(score, 4)
        return {
            "similarity_score": final_score,
            "similarity_percent": f"{final_score * 100:.1f}%",
            "breakdown": breakdown,
            "why_retrieved": why_retrieved
        }

    def compute_similarity(
        self,
        candidate_features: Dict[str, Any],
        historical_features: Dict[str, Any],
        policy_name: str = "DEFAULT"
    ) -> float:
        """
        Convenience function returning numeric similarity score.
        """
        return self.compute_similarity_with_policy(candidate_features, historical_features, policy_name)["similarity_score"]
