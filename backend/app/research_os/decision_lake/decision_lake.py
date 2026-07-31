import os
import json
import logging
import tempfile
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import pyarrow as pa
import pyarrow.parquet as pq

from app.research_os.governance.dataset_registry import RESEARCH_STORAGE_DIR, ensure_research_storage_structure

logger = logging.getLogger("research_os.decision_lake")

DECISION_LAKE_DIR = os.path.join(RESEARCH_STORAGE_DIR, "decision_lake")

DECISION_SCHEMA = pa.schema([
    ("decision_id", pa.string()),
    ("timestamp", pa.string()),
    ("timestamp_utc", pa.int64()),
    ("symbol", pa.string()),
    ("spot_price", pa.float64()),
    ("strategy_name", pa.string()),
    ("strategy_version", pa.string()),
    ("feature_version", pa.string()),
    ("prediction", pa.string()),
    ("confidence", pa.float64()),
    ("reason", pa.string()),
    ("created_date", pa.string()),
])


class DecisionLake:
    """
    Pipeline 6: AI-Ready Decision Lake.
    Persists every research decision event permanently in ZSTD Parquet storage.
    Enforces Requirement 6: Every stored decision records the exact `feature_version` used.
    """

    def __init__(self, base_dir: str = DECISION_LAKE_DIR):
        ensure_research_storage_structure()
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        self.decisions_json = os.path.join(self.base_dir, "decisions.json")
        self.decisions_parquet = os.path.join(self.base_dir, "decisions.parquet")

    def record_decision(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """
        Records a strategy prediction event into the Decision Lake.
        Ensures feature_version is present.
        """
        if "feature_version" not in decision:
            raise ValueError("Decision Lake Violation: Record missing mandatory 'feature_version' for reproducibility.")

        dec_id = f"DEC-{decision['symbol']}-{decision['timestamp_utc']}-{decision['strategy_name']}"
        entry = {
            "decision_id": dec_id,
            "timestamp": str(decision["timestamp"]),
            "timestamp_utc": int(decision["timestamp_utc"]),
            "symbol": str(decision["symbol"]).upper(),
            "spot_price": float(decision.get("spot_price", 0.0)),
            "strategy_name": str(decision["strategy_name"]),
            "strategy_version": str(decision["strategy_version"]),
            "feature_version": str(decision["feature_version"]),
            "prediction": str(decision.get("prediction", decision.get("signal", "NEUTRAL"))),
            "confidence": float(decision.get("confidence", 1.0)),
            "reason": str(decision.get("reason", "")),
            "created_date": datetime.now(timezone.utc).isoformat(),
        }

        existing = self.list_decisions()
        filtered = [e for e in existing if e["decision_id"] != dec_id]
        filtered.append(entry)

        # Write JSON & Parquet atomically
        self._write_json_atomic(filtered)
        self._write_parquet_atomic(filtered)
        logger.info("Recorded Decision '%s' (Strategy: %s, FeatureVersion: %s)", dec_id, entry["strategy_name"], entry["feature_version"])
        return entry

    def list_decisions(self) -> List[Dict[str, Any]]:
        """Lists recorded decision records from JSON index."""
        if not os.path.exists(self.decisions_json):
            return []
        try:
            with open(self.decisions_json, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _write_json_atomic(self, entries: List[Dict[str, Any]]):
        temp_dir = os.path.dirname(self.decisions_json)
        with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8") as tf:
            json.dump(entries, tf, indent=2)
            temp_name = tf.name
        os.replace(temp_name, self.decisions_json)

    def _write_parquet_atomic(self, entries: List[Dict[str, Any]]):
        if not entries:
            return
        temp_dir = os.path.dirname(self.decisions_parquet)
        with tempfile.NamedTemporaryFile("wb", dir=temp_dir, delete=False, suffix=".parquet") as tf:
            temp_name = tf.name

        table = pa.Table.from_pylist(entries, schema=DECISION_SCHEMA)
        pq.write_table(table, temp_name, compression="zstd")
        try:
            os.replace(temp_name, self.decisions_parquet)
        except PermissionError:
            pq.write_table(table, self.decisions_parquet, compression="zstd")
            try:
                os.remove(temp_name)
            except Exception:
                pass
