"""
Sprint AA — Internal Observation Graph & Collapse Model
Represents concurrent observations as a graph node-edge network G = (V, E)
and collapses the graph into unified situation candidates for the Situation Engine.
"""

from typing import List, Dict, Any, Set, Tuple
from collections import defaultdict

class ObservationGraph:
    """
    Graph Representation of concurrent market observations.
    Nodes: Observation IDs
    Edges: Co-occurrence / Categorical dependencies
    """

    def build_and_collapse(self, observations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Builds graph from snapshot observations and collapses it into candidate situation features.
        """
        nodes: Set[str] = set()
        categories: Set[str] = set()
        edges: List[Tuple[str, str]] = []
        max_severity = 1
        evidence_pool: Dict[str, Any] = {}

        for obs in observations:
            obs_id = obs.get("observation_id", "")
            cat = obs.get("category", "")
            sev_lvl = obs.get("severity_level", 1)

            nodes.add(obs_id)
            categories.add(cat)
            if sev_lvl > max_severity:
                max_severity = sev_lvl

            ev = obs.get("evidence", {})
            if isinstance(ev, dict):
                evidence_pool.update(ev)

        # Build co-occurrence edges between all active nodes
        node_list = sorted(list(nodes))
        for i in range(len(node_list)):
            for j in range(i + 1, len(node_list)):
                edges.append((node_list[i], node_list[j]))

        graph_density = round(len(edges) / max(1, (len(nodes) * (len(nodes) - 1)) / 2.0), 2) if len(nodes) > 1 else 1.0

        return {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "active_nodes": node_list,
            "categories": sorted(list(categories)),
            "graph_density": graph_density,
            "max_severity_level": max_severity,
            "evidence_pool": evidence_pool
        }
