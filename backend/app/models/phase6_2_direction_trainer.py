"""
🏛️ OI Lens — PHASE 6.2 DIRECTIONAL REASONING TRAINER (v1.0)

Trains and evaluates baseline models for:
- MOD_03_MARKET_DIRECTION (Multi-Horizon Directional Reasoning Engine)

Evaluates performance across Train (2021-23), Validation (2024), and Out-of-Time Test (2025-26).
Predicts multi-horizon directionality and excursion expectations.
"""

import os
import sys
import json
import time
import logging
from typing import Dict, Any, List

import numpy as np
import pyarrow.parquet as pq
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, log_loss
import lightgbm as lgb
from catboost import CatBoostClassifier

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from app.models.base_model_trainer import BaseModelTrainer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("phase6_2_direction_trainer")


class Phase62DirectionTrainer:

    def train_mod03_direction(self):
        log.info("=" * 80)
        log.info("TRAINING MOD_03_MARKET_DIRECTION MODEL (CatBoost / LightGBM Multi-Horizon)")
        log.info("=" * 80)

        trainer = BaseModelTrainer("MOD_03_MARKET_DIRECTION", "Market Direction Expectancy", "layer_2_reasoning")
        tbl_train, tbl_val, tbl_test, feat_cols, target_col = trainer.load_split_datasets()

        d_train = tbl_train.to_pydict()
        d_val = tbl_val.to_pydict()
        d_test = tbl_test.to_pydict()

        le_target = LabelEncoder()
        y_train = le_target.fit_transform(d_train[target_col])
        y_val = le_target.transform(d_val[target_col])
        y_test = le_target.transform(d_test[target_col])

        # Feature Extraction with categorical string hashing
        def extract_X(d_dict):
            rows = []
            for i in range(len(d_dict[target_col])):
                row = []
                for c in feat_cols:
                    val = d_dict[c][i]
                    if isinstance(val, str):
                        val = float(hash(val) % 1000)
                    row.append(float(val) if val is not None else 0.0)
                rows.append(row)
            return np.array(rows)

        log.info("[MOD_03] Extracting feature matrices for Train, Val, Test...")
        X_train = extract_X(d_train)
        X_val = extract_X(d_val)
        X_test = extract_X(d_test)

        # Train CatBoost Classifier for high directional precision
        params = {
            "iterations": 200,
            "depth": 6,
            "learning_rate": 0.05,
            "loss_function": "MultiClass",
            "verbose": 50,
            "random_seed": 42
        }

        log.info("[MOD_03] Training CatBoost Multi-Horizon Model across %d classes...", len(le_target.classes_))
        t_start = time.time()
        model = CatBoostClassifier(**params)
        model.fit(X_train, y_train, eval_set=(X_val, y_val), early_stopping_rounds=30)

        # Evaluate on Out-of-Time Test Set
        y_test_probs = model.predict_proba(X_test)
        y_test_preds = np.argmax(y_test_probs, axis=1)

        acc = accuracy_score(y_test, y_test_preds)
        prec, rec, f1, _ = precision_recall_fscore_support(y_test, y_test_preds, average="macro", zero_division=0)
        loss = log_loss(y_test, y_test_probs)

        # High-precision threshold evaluation (Directional Conviction > 70%)
        max_probs = np.max(y_test_probs, axis=1)
        high_conf_mask = max_probs >= 0.70
        if np.sum(high_conf_mask) > 0:
            high_conf_acc = accuracy_score(y_test[high_conf_mask], y_test_preds[high_conf_mask])
        else:
            high_conf_acc = acc

        log.info("[MOD_03 OUT-OF-TIME TEST RESULTS]: Overall Accuracy=%.4f, Macro F1=%.4f, LogLoss=%.4f", acc, f1, loss)
        log.info("[MOD_03 HIGH CONVICTION PREDICTION (>70%%)] Accuracy=%.4f (on %d samples)", high_conf_acc, int(np.sum(high_conf_mask)))

        # Feature Importance
        imp_scores = model.get_feature_importance()
        total_gain = sum(imp_scores) + 1e-6
        feat_imp = {feat_cols[i]: round(float(imp_scores[i] / total_gain * 100.0), 2) for i in range(len(feat_cols))}

        # Model Persistence
        model_file = "model.cbm"
        model.save_model(os.path.join(trainer.model_dir, model_file))

        metrics = {
            "test_accuracy": round(float(acc), 4),
            "high_conviction_accuracy_gt70": round(float(high_conf_acc), 4),
            "high_conviction_samples_pct": round(float(np.sum(high_conf_mask) / len(y_test) * 100.0), 2),
            "test_macro_f1": round(float(f1), 4),
            "test_log_loss": round(float(loss), 4),
            "training_time_sec": round(time.time() - t_start, 2)
        }

        trainer.save_model_manifest(metrics, feat_imp, params, model_file)
        return metrics


if __name__ == "__main__":
    trainer = Phase62DirectionTrainer()
    trainer.train_mod03_direction()
