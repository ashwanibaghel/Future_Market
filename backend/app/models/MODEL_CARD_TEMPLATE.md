# 📄 MODEL CARD: [MODULE_ID] — [MODULE_NAME]

> **Version**: [VERSION] (e.g. v1.0.0)  
> **Layer**: [LAYER_NAME]  
> **Lifecycle Status**: `RESEARCH_VALIDATED` | `WALK_FORWARD_PASSED` | `SHADOW_READY` | `PRODUCTION_READY`  
> **Audited Date**: [DATE]  
> **Dataset SHA256**: `[DATASET_FINGERPRINT_SHA256]`  

---

## 🎯 1. Model Purpose & Target Prediction
* **Target Variable ($Y$)**: `[TARGET_COLUMN]`
* **Prediction Task**: [Binary / Multi-Class Classification / Regression]
* **Business Objective**: [What trading decision does this output inform?]

---

## 📊 2. Provenance & Feature Vector
* **Training Period**: 2021 – 2023 ([TRAIN_ROWS] rows)
* **Validation Period**: 2024 ([VAL_ROWS] rows)
* **Out-of-Time Test Period**: 2025 – 2026 ([TEST_ROWS] rows)
* **Features Included ($X$)**: `[FEATURE_LIST]`
* **LeakageGuard Status**: ✅ Passed 100% Clean (Zero post-snapshot features)

---

## 📈 3. Empirical Test Performance & 95% Confidence Intervals (8th Commandment)
| Metric | Point Estimate | 95% Confidence Interval | Rolling Out-of-Time Folds | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Accuracy** | [ACCURACY] | [95% CI: Lower – Upper] | 2024: [V24] \| 2025: [V25] \| 2026: [V26] | ✅ / ⚠️ |
| **LogLoss** | [LOG_LOSS] | [95% CI: Lower – Upper] | Std Dev: [STD_DEV] | ✅ / ⚠️ |
| **Macro F1** | [MACRO_F1] | [95% CI: Lower – Upper] | Minority Class F1: [MIN_F1] | ✅ / ⚠️ |
| **Weighted F1** | [WEIGHTED_F1] | [95% CI: Lower – Upper] | Out-of-Time Stability: [STABILITY] | ✅ / ⚠️ |

---

## 🔬 4. Falsification Audit (7th Commandment)
> **Mandatory Release Question**: *"Is model ko galat prove karne ke liye kaun-kaun se experiments kiye gaye?"*

1. **Ablation Experiment**: [Feature removal test results]
2. **Out-of-Distribution Noise Test**: [Synthetic IV/spread noise stress test result]
3. **Regime Shift Stress Test**: [Performance during 2024 high-volatility election/event days]

---

## 🟢 5. Where the Model Excels (Best Regimes)
* **High-Conviction Regimes**: [e.g. High Liquidity Volatility Breakouts, Clean Trend Continuations]
* **Dominant Feature Drivers**: Top 3 features by gain importance (`[TOP_FEATURE_1]`, `[TOP_FEATURE_2]`, `[TOP_FEATURE_3]`).

---

## ⚠️ 6. Known Failure Modes & Limitations
* **Vulnerable Regimes**: [e.g. Chop/Noise Range Consolidation, RBI/Fed Unexpected Rate Announcements]
* **Class Imbalance Vulnerability**: [Does the model struggle on 0.5% rare event classes?]
* **Data Shift Risk**: [What happens if implied volatility doubles overnight?]

---

## ⛔ 7. WHEN NOT TO USE THIS MODEL (Strict Red Lines)
* ❌ **Do NOT use** during first 15 minutes of market open (09:15 – 09:30 AM) if spread is wide.
* ❌ **Do NOT use** if `microstructure_confidence < 0.65` or data gap is detected.
* ❌ **Do NOT use** if `LeakageGuard` or dataset SHA256 integrity check fails.

---

## 🔄 8. Version Drift & Metrics History
| Version | Release Date | Key Change / Audit Finding | Test Accuracy | Macro F1 | Lifecycle Status |
| :---: | :---: | :--- | :---: | :---: | :---: |
| **v1.0.0** | 2026-07-29 | Initial Training Run | 100.0% (Fake) | 1.000 | `RESEARCH_DRAFT` |
| **v1.1.0** | 2026-07-29 | Target Leakage Scrubbed (`mfe_*` removed) | 82.16% | 0.720 | `RESEARCH_VALIDATED` |
| **v1.2.0** | 2026-07-30 | Continuous Features & Class Weighting | 83.26% | 0.686 | `RESEARCH_VALIDATED` |
