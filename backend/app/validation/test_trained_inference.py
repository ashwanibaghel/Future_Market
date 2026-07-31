import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.engine.paper_trading_engine import global_paper_engine

res = global_paper_engine.step_playback("NIFTY")
print("================================================================================")
print("       REAL TRAINED MODEL INFERENCE STEP PLAYBACK RESULT (v1.0)               ")
print("================================================================================")
print("Candle Time :", res["current_candle_time"])
print("AI Decision :", res["current_ai_decision"]["decision"])
print("Reason      :", res["current_ai_decision"]["reason"])
print("Consensus % :", res["decision_fusion"]["consensus_pct"])
print("\nREAL TRAINED MODEL INFERENCES (.lgb / .cbm weights):")
for k, v in res["model_opinions"].items():
    print(f"  {k:<32} -> Opinion: {v['opinion']:<35} | Status: {v['status']}")
print("================================================================================\n")
