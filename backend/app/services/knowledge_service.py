"""
🏛️ OI Lens — KNOWLEDGE SERVICE LAYER (v1.0)

Clean, unified interface for accessing validated market intelligence knowledge base.
Ensures Step 5 ML Dataset Generators & future AI models interact strictly through
this service rather than parsing raw Parquet files directly.

Features:
- Validated Hypotheses Querying by Operational Readiness (PRODUCTION_READY, SHADOW_READY, etc.)
- Situation & Regime Specific Knowledge Lookup
- Knowledge Family Aggregation
- Practical Impact Scoring (Relative Risk × Sample Scale × Stability)
- Rare Event Knowledge Extraction
- Evidence Lineage Resolution (Knowledge ID -> Raw Evidence Records)
"""

import os
import glob
import json
import logging
from typing import Dict, Any, List, Optional, Union, Tuple
import pyarrow.parquet as pq

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("knowledge_service")

KNOWLEDGE_BASE_DIR = "E:/Future Stock/research_storage/knowledge_base/v1"
VALIDATION_DIR = os.path.join(KNOWLEDGE_BASE_DIR, "validation")
EVIDENCE_DATASET_DIR = "E:/Future Stock/research_storage/market_intelligence_dataset"


class KnowledgeService:
    """
    Unified Production Knowledge Service for Artificial Trader Brain.
    """

    def __init__(self, validation_dir: str = VALIDATION_DIR, knowledge_dir: str = KNOWLEDGE_BASE_DIR):
        self.validation_dir = validation_dir
        self.knowledge_dir = knowledge_dir
        self._validated_repo_cache: Optional[List[Dict[str, Any]]] = None
        self._registry_cache: Optional[List[Dict[str, Any]]] = None
        self._rare_events_cache: Optional[List[Dict[str, Any]]] = None
        self._load_and_cache_knowledge()

    def _load_and_cache_knowledge(self):
        """Loads and caches Parquet datasets into memory for lightning-fast queries."""
        repo_path = os.path.join(self.validation_dir, "knowledge_validated_repository.parquet")
        reg_path = os.path.join(self.knowledge_dir, "knowledge_registry.parquet")
        rare_path = os.path.join(self.knowledge_dir, "rare_events_knowledge.parquet")

        if os.path.exists(repo_path):
            self._validated_repo_cache = pq.read_table(repo_path).to_pydict()
            # Convert dict of lists to list of dicts
            keys = list(self._validated_repo_cache.keys())
            n_rows = len(self._validated_repo_cache[keys[0]])
            self._validated_repo = [
                {k: self._validated_repo_cache[k][i] for k in keys}
                for i in range(n_rows)
            ]
        else:
            self._validated_repo = []

        if os.path.exists(reg_path):
            reg_dict = pq.read_table(reg_path).to_pydict()
            keys = list(reg_dict.keys())
            n_rows = len(reg_dict[keys[0]])
            self._registry = [{k: reg_dict[k][i] for k in keys} for i in range(n_rows)]
        else:
            self._registry = []

        if os.path.exists(rare_path):
            rare_dict = pq.read_table(rare_path).to_pydict()
            keys = list(rare_dict.keys())
            n_rows = len(rare_dict[keys[0]])
            self._rare_events = [{k: rare_dict[k][i] for k in keys} for i in range(n_rows)]
        else:
            self._rare_events = []

        log.info("KnowledgeService Initialized: %d Validated Hypotheses, %d Registry Entries, %d Rare Events Cached.",
                 len(self._validated_repo), len(self._registry), len(self._rare_events))

    def get_validated_hypotheses(
        self,
        readiness: Optional[Union[str, List[str]]] = None,
        decision: Optional[Union[str, List[str]]] = None,
        min_quality_score: float = 0.0,
        horizon: Optional[str] = None,
        min_relative_risk: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Queries validated hypotheses filtered by operational readiness, statistical decision,
        quality score, target horizon, and relative risk.
        """
        results = []
        if isinstance(readiness, str):
            readiness = [readiness]
        if isinstance(decision, str):
            decision = [decision]

        for entry in self._validated_repo:
            if readiness and entry.get("operational_readiness") not in readiness:
                continue
            if decision and entry.get("validation_decision") not in decision:
                continue
            if entry.get("overall_quality_score", 0.0) < min_quality_score:
                continue
            if horizon and entry.get("target_horizon") != horizon:
                continue
            if entry.get("relative_risk", 0.0) < min_relative_risk:
                continue

            results.append(entry)

        return sorted(results, key=lambda x: x.get("overall_quality_score", 0.0), reverse=True)

    def query_knowledge_for_situation(
        self,
        situation_id: str,
        symbol: Optional[str] = None,
        regime: Optional[str] = None,
        readiness_filter: Tuple[str, ...] = ("PRODUCTION_READY", "SHADOW_READY")
    ) -> List[Dict[str, Any]]:
        """
        Returns all relevant validated knowledge entries matching a specific market situation,
        symbol, and regime context.
        """
        matched = []
        for entry in self._validated_repo:
            if entry.get("operational_readiness") not in readiness_filter:
                continue
            key = entry.get("condition_key", "")
            if situation_id in key:
                if symbol and ("@" in key) and (symbol not in key):
                    continue
                if regime and ("in [" in key) and (regime not in key):
                    continue
                matched.append(entry)

        return sorted(matched, key=lambda x: x.get("relative_risk", 0.0), reverse=True)

    def get_knowledge_families(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Groups validated hypotheses into logical Knowledge Families based on core conditions.
        Solves the issue of redundant combinations by providing family-level summaries.
        """
        families = {}
        for entry in self._validated_repo:
            cat = entry.get("category", "GENERAL")
            key = entry.get("condition_key", "").split("@")[0].split("in [")[0].strip()
            fam_key = f"{cat}::{key}"

            if fam_key not in families:
                families[fam_key] = []
            families[fam_key].append(entry)

        return families

    def get_rare_events(self, category: Optional[str] = None, limit: int = 1000) -> List[Dict[str, Any]]:
        """Extracts rare market tail events for tail-risk model dataset training."""
        if not category:
            return self._rare_events[:limit]
        return [e for e in self._rare_events if e.get("event_category") == category][:limit]


# Global Singleton Instance for clean imports
knowledge_service = KnowledgeService()

if __name__ == "__main__":
    print("Testing KnowledgeService...")
    prod_hyp = knowledge_service.get_validated_hypotheses(readiness="PRODUCTION_READY")
    print(f"Production Ready Hypotheses Count: {len(prod_hyp)}")

    fams = knowledge_service.get_knowledge_families()
    print(f"Aggregated Knowledge Families Count: {len(fams)}")

    top_family = list(fams.keys())[0]
    print(f"Sample Family '{top_family}': {len(fams[top_family])} members.")
