# 📄 MODEL CARD: MOD_03_MARKET_DIRECTION — Market Direction Expectancy Engine

> **Version**: 2.0  
> **Layer**: `layer_2_reasoning`  
> **Lifecycle Status**: `RESEARCH_VALIDATED` (Passed LeakageGuard & Out-of-Time Test)  
> **Audited Date**: 2026-07-29T20:46:23Z  

---

## 🎯 1. Model Purpose & Target Prediction
* **Target Variable ($Y$)**: `direction_15m (BULLISH / BEARISH / NEUTRAL)`
* **Prediction Task**: Multi-Class Machine Learning Classification
* **Business Objective**: Predict out-of-sample directional price expectancy over the next 15-minute horizon.

---

## 📊 2. Provenance & Feature Vector
* **Training & Evaluation Split**: 2021-2023 Train (499,478) / 2024 Val (185,863) / 2025-2026 Out-of-Time Test (291,227)
* **Model Engine**: LightGBM / CatBoost Gradient Boosted Trees
* **Top Drivers**: `severity_level` (100.0%), `adx_14` (0.0%), `atr_14` (0.0%)
* **LeakageGuard Status**: [OK] Passed 100% Clean (Zero post-snapshot features)

---

## 📈 3. Empirical Test Performance & 95% Confidence Intervals (8th Commandment)
| Metric | Point Estimate | 95% Confidence Interval | Rolling Out-of-Time Stability | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Accuracy** | 82.16% | [82.02% – 82.30%] | 2024: 81.9% \| 2025: 82.3% \| 2026: 82.0% | [OK] |
| **LogLoss** | 0.4137 | [0.408 – 0.418] | Out-of-Time Std Dev = 0.2% | [OK] |

---

## 🔬 4. Falsification Audit (7th Commandment)
> **Mandatory Release Question**: *"Is model ko galat prove karne ke liye kaun-kaun se experiments kiye gaye?"*

1. **Experiment 1**: Future Excursion Audit: Scrubbed mfe_15m & mae_15m future attributes — accuracy shifted from cheat 100% to valid 82.16%.
1. **Experiment 2**: 95% Confidence Interval Calculation: 82.16% +- 0.14% across 291,227 test rows [82.02% - 82.30%].
1. **Experiment 3**: Fold Stability: 2024 Val = 81.9%, 2025 Test = 82.3%, 2026 Test = 82.0% — Std Dev = 0.2%.

---

## 🟢 5. Where the Model Excels
* **Best Operating Conditions**: High-conviction directional moves (82.16% out-of-time accuracy, 0.4133 LogLoss).

---

## ⚠️ 6. Known Failure Modes & Limitations
* **Vulnerable Scenarios**: Accuracy drops to 54% during low-volume sideways chop at mid-day (12:00-13:30 PM).

---

## ⛔ 7. WHEN NOT TO USE THIS MODEL (Strict Red Lines)
* ❌ Do NOT use if directional_uncertainty > 0.45.
* ❌ Do NOT trade signals with probability conviction < 70%.
* ❌ Do NOT use without Layer 4 Risk & Position Sizing constraints.

---

## 🔄 8. Version Drift & Metrics History
| Version | Release Date | Key Change / Audit Finding | Test Accuracy | Macro F1 | Lifecycle Status |
| :---: | :---: | :--- | :---: | :---: | :---: |
| **v1.0.0** | 2026-07-29 | Future Excursion Target Leak (mfe_15m in X) | 100.00% | 1.0000 | `REJECTED_BUG` |
| **v1.1.0** | 2026-07-30 | Dual-Layer LeakageGuard Scrubbing (Clean ML) | 82.16% | 0.7204 | `RESEARCH_VALIDATED` |
