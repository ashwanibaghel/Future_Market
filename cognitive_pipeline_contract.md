# OI Lens Cognitive Pipeline Contract

> **Non-Negotiable Scope Governance & Contract Definitions Across Cognitive AI Layers**

---

| Cognitive Layer | Input Data | Primary Output | Strict Boundaries ("Cannot Do") |
| :--- | :--- | :--- | :--- |
| **Observe (`Sprint Z`)** | Raw Market Snapshots | Quantitative Observations | **Cannot infer trading context or decisions.** |
| **Understand (`Sprint AA`)** | Observations | Situation Timelines & 4-Pillar Context | **Cannot infer trade signals or price targets.** |
| **Remember (`Sprint AB`)** | Situation Timelines | Immutable Episodic Memories & Outcomes | **Cannot modify past memory records.** |
| **Retrieve (`Sprint AC`)** | Situation Fingerprint | Top-10 Similar Memories & Match Rationales | **Cannot formulate hypotheses or make trade decisions.** |
| **Synthesize (`Sprint AD`)** | Top-K Memories | Empirical Evidence & Structural Hypotheses | **Cannot emit buy/sell decisions or execution plans.** |
| **Reason (`Sprint AE`)** | Synthesized Hypotheses | Multi-Hypothesis Competing Reasoning Chain | **Cannot generate execution orders, single predictions, or discard minority evidence.** |
| **Decide (`Sprint AF`)** | Reasoning Assessment | Risk-Attributed Strategy & Position Plan | **Cannot rewrite history or learn directly without feedback.** |
| **Learn (`Phase 5`)** | Physical Trade Outcomes | Updated Knowledge Base Parameters | **Cannot alter historical memory facts.** |

---

## 📜 GOVERNANCE & ARCHITECTURE FREEZE v1.0
1. This contract strictly prevents scope creep and ensures every cognitive layer maintains 100% decoupled responsibility and explainable output.
2. **Minority Evidence Preservation Rule**: *The Reasoning Engine must never discard minority or contradicting evidence. Contradicting evidence must remain visible in reasoning chains until invalidated by empirical evidence.*
