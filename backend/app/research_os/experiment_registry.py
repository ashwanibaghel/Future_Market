"""
🏛️ RESEARCH OS — IMMUTABLE EXPERIMENT REGISTRY ENGINE (v1.0)

Role:
- Maintains persistent, immutable records of all scientific experiments, hypotheses, & validation results
- Tracks: Experiment ID, Objective, Hypothesis, Dataset Version, Model Version, Expected Result, Actual Result, Decision
- Prevents knowledge loss over 100+ research iterations
"""

import os
import sys
import json
import time
from typing import Dict, Any, List, Optional

EXPERIMENT_REGISTRY_FILE = "E:/Future Stock/research_storage/experiment_registry.json"
QUALITY_REPORTS_DIR = "E:/Future Stock/research_storage/quality_reports"
os.makedirs(QUALITY_REPORTS_DIR, exist_ok=True)


class ExperimentRegistry:
    def __init__(self, registry_path: str = EXPERIMENT_REGISTRY_FILE):
        self.registry_path = registry_path
        self.experiments = self.load_registry()

    def load_registry(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.registry_path):
            with open(self.registry_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def register_experiment(
        self,
        exp_id: str,
        objective: str,
        hypothesis: str,
        dataset_version: str,
        model_version: str,
        expected_result: str,
        actual_result: str,
        decision: str,  # "ACCEPTED" or "REJECTED"
        rationale: str
    ) -> Dict[str, Any]:
        """Registers an immutable experiment record."""
        record = {
            "experiment_id": exp_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "objective": objective,
            "hypothesis": hypothesis,
            "dataset_version": dataset_version,
            "model_version": model_version,
            "expected_result": expected_result,
            "actual_result": actual_result,
            "decision": decision,
            "rationale": rationale
        }
        self.experiments.append(record)
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(self.experiments, f, indent=2)

        self.generate_registry_report()
        return record

    def generate_registry_report(self) -> str:
        report_path = os.path.join(QUALITY_REPORTS_DIR, "experiment_registry_report.md")
        tot = len(self.experiments)
        accepted = sum(1 for e in self.experiments if e.get("decision") == "ACCEPTED")
        rejected = sum(1 for e in self.experiments if e.get("decision") == "REJECTED")

        md_lines = [
            "# 🧪 RESEARCH OS — IMMUTABLE EXPERIMENT REGISTRY REPORT",
            "",
            "> **Role**: Scientific tracking of all research hypotheses, experiments, & decisions.",
            f"> **Total Registered Experiments**: `{tot}` | **Accepted**: `{accepted}` | **Rejected**: `{rejected}`",
            "",
            "| Exp ID | Objective | Hypothesis | Dataset | Model | Expected vs Actual Result | Decision | Rationale |",
            "| :--- | :--- | :--- | :---: | :---: | :--- | :---: | :--- |"
        ]

        for e in reversed(self.experiments[-20:]):
            dec = e.get("decision", "ACCEPTED")
            dec_badge = "🟢 ACCEPTED" if dec == "ACCEPTED" else "🔴 REJECTED"
            res_str = f"Exp: {e.get('expected_result')}<br>Act: {e.get('actual_result')}"
            md_lines.append(f"| **{e['experiment_id']}** | {e['objective']} | {e['hypothesis']} | `{e['dataset_version']}` | `{e['model_version']}` | {res_str} | {dec_badge} | {e['rationale']} |")

        content = "\n".join(md_lines)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(content)

        return report_path


if __name__ == "__main__":
    reg = ExperimentRegistry()
    reg.register_experiment(
        exp_id="EXP-2026-001",
        objective="Scrub target-derivation leak in MOD_02 Regime Understanding",
        hypothesis="Replacing trend/vol/struct target derivation with continuous ADX/ATR will eliminate fake 100% accuracy.",
        dataset_version="v1.0.0-phase1-freeze",
        model_version="v1.0.0",
        expected_result="Test Accuracy ~80%-85%",
        actual_result="Clean ML Accuracy = 81.86%, LogLoss = 0.5547",
        decision="ACCEPTED",
        rationale="LeakageGuard passed cleanly. Model generalizes out-of-time without target leak."
    )
    print("Registered initial experiment in Experiment Registry.")
