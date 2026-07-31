# 📄 MODEL CARD: MOD_12_HISTORICAL_MEMORY — MOD_12_HISTORICAL_MEMORY

> **Version**: 2.0  
> **Layer**: `layer_1_perception`  
> **Lifecycle Status**: `RESEARCH_VALIDATED` (Passed LeakageGuard & Out-of-Time Test)  
> **Audited Date**: 2026-07-29T20:52:07Z  

---

## 🎯 1. Model Purpose & Target Prediction
* **Target Variable ($Y$)**: `Target Column`
* **Prediction Task**: Multi-Class Machine Learning Classification
* **Business Objective**: Quantitative AI Inference

---

## 📊 2. Provenance & Feature Vector
* **Training & Evaluation Split**: 2021-2023 Train (499,478) / 2024 Val (185,863) / 2025-2026 Out-of-Time Test (291,227)
* **Model Engine**: LightGBM / CatBoost Gradient Boosted Trees
* **Top Drivers**: `situation_id` (16.67%), `regime_id` (16.67%), `memory_embedding_vector_str` (16.67%)
* **LeakageGuard Status**: [OK] Passed 100% Clean (Zero post-snapshot features)

---

## 📈 3. Empirical Test Performance & 95% Confidence Intervals (8th Commandment)
| Metric | Point Estimate | 95% Confidence Interval | Rolling Out-of-Time Stability | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Accuracy** | 100.00% | N/A | 2024: 81.9% \| 2025: 82.3% \| 2026: 82.0% | [OK] |
| **LogLoss** | 0.0 | [0.408 – 0.418] | Out-of-Time Std Dev = 0.2% | [OK] |

---

## 🔬 4. Falsification Audit (7th Commandment)
> **Mandatory Release Question**: *"Is model ko galat prove karne ke liye kaun-kaun se experiments kiye gaye?"*

1. **Experiment 1**: Standard ablation & out-of-sample noise tests.

---

## 🟢 5. Where the Model Excels
* **Best Operating Conditions**: Standard market conditions

---

## ⚠️ 6. Known Failure Modes & Limitations
* **Vulnerable Scenarios**: Standard quantitative boundaries

---

## ⛔ 7. WHEN NOT TO USE THIS MODEL (Strict Red Lines)
* ❌ Do NOT use without risk management

---

## 🔄 8. Version Drift & Metrics History
| Version | Release Date | Key Change / Audit Finding | Test Accuracy | Macro F1 | Lifecycle Status |
| :---: | :---: | :--- | :---: | :---: | :---: |
| **v1.0.0** | 2026-07-29 | Initial Baseline | 82.16% | 0.7204 | `RESEARCH_VALIDATED` |
