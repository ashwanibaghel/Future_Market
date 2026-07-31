"""
🏛️ OI Lens — PHASE 6.1 PERCEPTION FOUNDATION TRAINER (v1.0)

Trains and evaluates baseline models for:
1. MOD_01_SITUATION_DISCOVERY (XGBoost / LightGBM Situation Classifier)
2. MOD_02_REGIME_UNDERSTANDING (LightGBM Macro Regime Classifier)

Evaluates performance across Train (2021-23), Validation (2024), and Out-of-Time Test (2025-26).
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

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from app.models.base_model_trainer import BaseModelTrainer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("phase6_1_perception_trainer")


class Phase61PerceptionTrainer:

    def train_mod01_situation(self):
        log.info("=" * 80)
        log.info("TRAINING MOD_01_SITUATION_DISCOVERY MODEL (LightGBM Multi-Class)")
        log.info("=" * 80)

        trainer = BaseModelTrainer("MOD_01_SITUATION_DISCOVERY", "Situation Discovery", "layer_1_perception")
        tbl_train, tbl_val, tbl_test, feat_cols, target_col = trainer.load_split_datasets()

        d_train = tbl_train.to_pydict()
        d_val = tbl_val.to_pydict()
        d_test = tbl_test.to_pydict()

        # Encode categorical features and target
        le_target = LabelEncoder()
        y_train = le_target.fit_transform(d_train[target_col])
        y_val = le_target.transform(d_val[target_col])
        y_test = le_target.transform(d_test[target_col])

        # Prepare X arrays
        def extract_X(d_dict):
            rows = []
            for i in range(len(d_dict[target_col])):
                row = []
                for c in feat_cols:
                    val = d_dict[c][i]
                    if isinstance(val, str):
                        # Simple categorical hashing for strings
                        val = float(hash(val) % 1000)
                    row.append(float(val) if val is not None else 0.0)
                rows.append(row)
            return np.array(rows)

        X_train = extract_X(d_train)
        X_val = extract_X(d_val)
        X_test = extract_X(d_test)

        # Train LightGBM Multi-Class Model
        params = {
            "objective": "multiclass",
            "num_class": len(le_target.classes_),
            "metric": "multi_logloss",
            "boosting_type": "gbdt",
            "learning_rate": 0.05,
            "num_leaves": 31,
            "max_depth": 6,
            "verbose": -1,
            "random_state": 42
        }

        train_data = lgb.Dataset(X_train, label=y_train)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

        log.info("[MOD_01] Fitting LightGBM model across %d classes...", len(le_target.classes_))
        t_start = time.time()
        model = lgb.train(params, train_data, num_boost_round=150, valid_sets=[val_data])

        # Evaluate on Test Set
        y_test_probs = model.predict(X_test)
        y_test_preds = np.argmax(y_test_probs, axis=1)

        acc = accuracy_score(y_test, y_test_preds)
        prec, rec, f1, _ = precision_recall_fscore_support(y_test, y_test_preds, average="macro")
        loss = log_loss(y_test, y_test_probs)

        log.info("[MOD_01 OUT-OF-TIME TEST RESULTS]: Accuracy=%.4f, Macro F1=%.4f, LogLoss=%.4f", acc, f1, loss)

        # Feature Importance
        imp_scores = model.feature_importance(importance_type="gain")
        total_gain = sum(imp_scores) + 1e-6
        feat_imp = {feat_cols[i]: round(float(imp_scores[i] / total_gain * 100.0), 2) for i in range(len(feat_cols))}

        # Persistence
        model_file = "model.lgb"
        model.save_model(os.path.join(trainer.model_dir, model_file))

        metrics = {
            "test_accuracy": round(float(acc), 4),
            "test_macro_f1": round(float(f1), 4),
            "test_log_loss": round(float(loss), 4),
            "target_classes_count": len(le_target.classes_),
            "training_time_sec": round(time.time() - t_start, 2)
        }

        trainer.save_model_manifest(metrics, feat_imp, params, model_file)
        return metrics

    def train_mod02_regime(self):
        log.info("=" * 80)
        log.info("TRAINING MOD_02_REGIME_UNDERSTANDING MODEL (LightGBM Multi-Class)")
        log.info("=" * 80)

        trainer = BaseModelTrainer("MOD_02_REGIME_UNDERSTANDING", "Regime Understanding", "layer_1_perception")
        tbl_train, tbl_val, tbl_test, feat_cols, target_col = trainer.load_split_datasets()

        d_train = tbl_train.to_pydict()
        d_val = tbl_val.to_pydict()
        d_test = tbl_test.to_pydict()

        le_target = LabelEncoder()
        y_train = le_target.fit_transform(d_train[target_col])
        y_val = le_target.transform(d_val[target_col])
        y_test = le_target.transform(d_test[target_col])

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

        X_train = extract_X(d_train)
        X_val = extract_X(d_val)
        X_test = extract_X(d_test)

        params = {
            "objective": "multiclass",
            "num_class": len(le_target.classes_),
            "metric": "multi_logloss",
            "boosting_type": "gbdt",
            "learning_rate": 0.05,
            "num_leaves": 31,
            "max_depth": 6,
            "verbose": -1,
            "random_state": 42
        }

        train_data = lgb.Dataset(X_train, label=y_train)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

        log.info("[MOD_02] Fitting LightGBM model across %d regime classes...", len(le_target.classes_))
        t_start = time.time()
        model = lgb.train(params, train_data, num_boost_round=150, valid_sets=[val_data])

        y_test_probs = model.predict(X_test)
        y_test_preds = np.argmax(y_test_probs, axis=1)

        acc = accuracy_score(y_test, y_test_preds)
        prec, rec, f1, _ = precision_recall_fscore_support(y_test, y_test_preds, average="macro")
        loss = log_loss(y_test, y_test_probs)

        log.info("[MOD_02 OUT-OF-TIME TEST RESULTS]: Accuracy=%.4f, Macro F1=%.4f, LogLoss=%.4f", acc, f1, loss)

        imp_scores = model.feature_importance(importance_type="gain")
        total_gain = sum(imp_scores) + 1e-6
        feat_imp = {feat_cols[i]: round(float(imp_scores[i] / total_gain * 100.0), 2) for i in range(len(feat_cols))}

        model_file = "model.lgb"
        model.save_model(os.path.join(trainer.model_dir, model_file))

        metrics = {
            "test_accuracy": round(float(acc), 4),
            "test_macro_f1": round(float(f1), 4),
            "test_log_loss": round(float(loss), 4),
            "target_classes_count": len(le_target.classes_),
            "training_time_sec": round(time.time() - t_start, 2)
        }

        trainer.save_model_manifest(metrics, feat_imp, params, model_file)
        return metrics

    def run_phase6_1_training(self):
        m1 = self.train_mod01_situation()
        m2 = self.train_mod02_regime()
        log.info("PHASE 6.1 PERCEPTION FOUNDATION TRAINING COMPLETE!")
        return m1, m2


if __name__ == "__main__":
    trainer = Phase61PerceptionTrainer()
    trainer.run_phase6_1_training()
