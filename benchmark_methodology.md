# OI Lens Benchmark Methodology & Scientific Credibility Standard

> **Document Status**: `Approved Standard`  
> **Target System**: `OI Lens Phase-2 Scientific Validation`  
> **Philosophy**: *"Evidence first. Conclusions second."*  
> **Language Standard**: *"Use cautious scientific phrasing (suggests, is consistent with the possibility that) instead of definitive claims (proves, indicates)."*

---

## 🏛️ 1. Expert Selection & Alignment Rubric

### 1.1 Expert Selection Criteria
To serve as a ground-truth benchmark for AI options market reasoning, human experts must meet the following mandatory qualification criteria:
- **Minimum Experience**: $\ge 5$ years of professional NSE F&O discretionary trading or quantitative market research experience.
- **Independence**: Blind evaluation of historical option chain snapshots without prior knowledge of AI system outputs or forward price movement.
- **Evaluation Format**: Standardized structuring of dominant hypotheses ($H_A$), failure clusters ($H_B$), missing information sources, and execution readiness assessments.

---

## 📊 2. Agreement Calculation Formula & Scoring

### 2.1 Agreement Metrics

#### A. Primary Hypothesis Alignment ($A_H$)
Calculated as the agreement rate between human expert primary structural view ($H_{expert}$) and AI dominant structural hypothesis ($H_{AI}$):
$$A_H = \frac{1}{N} \sum_{i=1}^{N} \mathbb{I}(H_{expert, i} \equiv H_{AI, i})$$

#### B. Contradiction & Failure Cluster Alignment ($A_C$)
Calculated as the agreement rate for identified risk/failure modes:
$$A_C = \frac{1}{N} \sum_{i=1}^{N} \text{JaccardSimilarity}(C_{expert, i}, C_{AI, i})$$

#### C. Unknown Information Source Alignment ($A_U$)
Calculated as the overlap between missing data sources identified by the expert and information gaps flagged by the AI:
$$A_U = \frac{1}{N} \sum_{i=1}^{N} \frac{|U_{expert, i} \cap U_{AI, i}|}{|U_{expert, i} \cup U_{AI, i}|}$$

---

## 🔬 3. External Stability & Robustness Metrics (Live Shadow Mode)

| External Metric | Definition & Meaning | Rationale |
| :--- | :--- | :--- |
| **Assessment Stability** | Similarity score when replaying identical market states | Ensures zero stochastic drift |
| **Reasoning Drift Rate** | Delta in reasoning chain over 5-minute intra-situation updates | Measures situational continuity |
| **Unknown Resolution Rate** | % of missing information sources resolved as live data streams in | Quantifies information gap reduction |
| **Audit Reproducibility %** | Verification rate where identical inputs produce identical hash outputs | Guarantees 100% deterministic auditing |

---

## 📉 4. Mandatory Negative Result Policy

Every scientific report must include a dedicated section: **"Findings That DID NOT Support Our Expectations"**.

### Mandatory Disclosures:
- **Expectation Failures**: Documenting cases where parameter adjustments (e.g. $K=20$) failed to improve execution readiness or reduce confidence conservatism.
- **Unresolved Information Gaps**: Disclosing persistent bottlenecks that cannot be resolved without new data feeds.
- **Unchanged Contradiction Rates**: Reporting when failure cluster frequencies remain static despite increased sample sizes.

---

## 📝 5. Publication-Quality Language Policy

To eliminate confirmation bias, all future scientific reporting must adhere to strict vocabulary constraints:

| Prohibited Definitive Term | Mandatory Scientific Replacement |
| :--- | :--- |
| **"Proves that..."** | **"Is consistent with the possibility that..."** / **"Suggests that..."** |
| **"Definitive proof of..."** | **"Provides empirical evidence supporting..."** |
| **"Universally indicates..."** | **"Within this benchmark sample, suggests..."** |
| **"Structural reality of market"** | **"Observed structural characteristic of dataset"** |
| **"Achieved 100% agreement"** | **"Within the current benchmark sample of N evaluated trading days, the measured agreement was 100%. Further validation on larger datasets is required before generalizing this result."** |

---

## 🔒 6. Reproducibility & Auditability Guarantee

Every benchmark evaluation must store an immutable audit package containing:
- `snapshot_timestamp`
- `expert_eval_id`
- `ai_decision_id`
- `traceability_tier_list`
- `reproducibility_hash`
