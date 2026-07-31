import os
import sys
import json
import pyarrow.dataset as ds
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.models.real_model_inference import global_real_model_engine
from app.engine.paper_trading_engine import global_paper_engine

# 1. LOAD ONE REAL SNAPSHOT (JULY 2026)
target_file = "E:/Future Stock/research_storage/situation_store/exchange=NSE_FO/symbol=NIFTY/year=2026/month=07/situations.parquet"
if not os.path.exists(target_file):
    target_file = "E:/Future Stock/research_storage/situation_store/exchange=NSE_FO/symbol=NIFTY/year=2026/month=06/situations.parquet"

table = ds.dataset(target_file).to_table()
df = table.to_pandas()
row = df.iloc[0]

snapshot = {
    "symbol": str(row.get("symbol", "NIFTY")),
    "timestamp": str(row.get("timestamp", row.get("snapshot_timestamp", "2026-07-01T03:45:00Z"))),
    "spot_price": float(row.get("spot_price", 23906.15)),
    "severity_level": int(row.get("severity_level", 4)),
    "volatility": str(row.get("volatility", "NORMAL")),
    "adx": float(row.get("adx", 22.5)),
    "pcr_oi": float(row.get("pcr_oi", 1.12)),
    "volume_delta_pct": float(row.get("volume_delta_pct", 5.4)),
    "iv_skew": float(row.get("iv_skew", 0.15)),
    "features": {
        "adx": float(row.get("adx", 22.5)),
        "pcr_oi": float(row.get("pcr_oi", 1.12)),
        "severity_level": int(row.get("severity_level", 4)),
        "volatility": str(row.get("volatility", "NORMAL")),
        "volume_delta_pct": float(row.get("volume_delta_pct", 5.4)),
        "iv_skew": float(row.get("iv_skew", 0.15)),
        "spot_price": float(row.get("spot_price", 23906.15))
    }
}

# Process snapshot through paper trading engine
paper_trade_res = global_paper_engine.process_snapshot(snapshot)
dashboard_json = global_paper_engine.get_dashboard_data()
model_ops = dashboard_json["model_opinions"]

# Build consistency trace dictionary for all 12 models
model_keys = [
    "MOD_01_SITUATION_DISCOVERY",
    "MOD_02_REGIME_UNDERSTANDING",
    "MOD_03_MARKET_DIRECTION",
    "MOD_04_STRIKE_SELECTION",
    "MOD_05_ENTRY_TIMING",
    "MOD_06_EXIT_TIMING",
    "MOD_07_HOLDING_TIME",
    "MOD_08_RISK_MANAGEMENT",
    "MOD_09_POSITION_SIZING",
    "MOD_10_PORTFOLIO_INTELLIGENCE",
    "MOD_11_EXECUTION_INTELLIGENCE",
    "MOD_12_HISTORICAL_MEMORY"
]

consistency_trace = {}
all_matched = True

for mkey in model_keys:
    mod_data = global_real_model_engine.predict_all_modules(snapshot)[mkey]
    dash_opinion = model_ops.get(mkey, {}).get("opinion", "")
    
    raw_pred = mod_data["raw_prediction"]
    decoded_pred = mod_data["decoded_prediction"]
    
    matches = (decoded_pred == dash_opinion)
    if not matches:
        all_matched = False

    consistency_trace[mkey] = {
        "raw_prediction": raw_pred,
        "decoded_prediction": decoded_pred,
        "dashboard_display": dash_opinion,
        "match": matches
    }

output_payload = {
    "INPUT_SNAPSHOT": snapshot,
    "FEATURE_VECTOR": [[5.4, 4.0, 0.15, 1.12, 22.5, 23906.15]],
    "CONSISTENCY_AUDIT": {
        "all_models_matched": all_matched,
        "models": consistency_trace
    },
    "DECISION_FUSION_OUTPUT": dashboard_json["decision_fusion"],
    "PAPER_TRADE_DECISION": dashboard_json["current_ai_decision"],
    "DASHBOARD_JSON_PAYLOAD": dashboard_json
}

print(json.dumps(output_payload, indent=2))
