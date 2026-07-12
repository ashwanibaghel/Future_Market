from __future__ import annotations


def build_knowledge_graph(dataset: dict, rule_audit: dict, pattern_intelligence: dict, execution_intelligence: dict, lineage: dict) -> dict:
    nodes = [
        {"id": "dataset", "label": "Dataset", "type": "domain", "score": dataset.get("feature_quality", 0.0)},
        {"id": "labels", "label": "Labels", "type": "quality", "score": dataset.get("label_coverage", 0.0)},
        {"id": "lineage", "label": "Lineage", "type": "governance", "score": dataset.get("lineage_coverage", 0.0)},
        {"id": "patterns", "label": "Patterns", "type": "research", "score": pattern_intelligence.get("average_pattern_confidence", 0.0)},
        {"id": "signals", "label": "Signals", "type": "research", "score": rule_audit.get("accuracy_pct", 0.0)},
        {"id": "execution", "label": "Execution", "type": "future_ml", "score": min(execution_intelligence.get("readiness", {}).values() or [0.0])},
    ]
    edges = [
        {"from": "dataset", "to": "labels", "relationship": "produces"},
        {"from": "dataset", "to": "patterns", "relationship": "feeds"},
        {"from": "lineage", "to": "patterns", "relationship": "explains"},
        {"from": "patterns", "to": "signals", "relationship": "contextualizes"},
        {"from": "signals", "to": "execution", "relationship": "creates_future_training_rows"},
    ]

    questions = {
        "Why is BUY PUT accuracy low?": [
            "Check bearish session count and DOWN label coverage.",
            f"Current label coverage is {dataset.get('label_coverage', 0.0)}%.",
            f"Missing Greeks pressure is {dataset.get('missing_greeks_pct', 0.0)}%.",
            f"Rule calibration gap is {rule_audit.get('signal_quality', {}).get('calibration_gap', 0.0)}.",
            "Replay validation should be used before any threshold change.",
        ],
        "What blocks execution models?": execution_intelligence.get("blockers", []),
        "Is research reproducible?": [
            f"Dataset versions: {', '.join(lineage.get('versions', {}).get('dataset_versions', []) or ['none'])}.",
            f"Engine versions: {', '.join(lineage.get('versions', {}).get('engine_versions', []) or ['none'])}.",
            f"Version consistency: {lineage.get('versions', {}).get('version_consistency', False)}.",
        ],
    }

    return {
        "engine": "Knowledge Graph",
        "status": "READY",
        "nodes": nodes,
        "edges": edges,
        "question_bank": questions,
        "rule": "Answers are generated from Mission Control metrics, not manual search.",
    }

