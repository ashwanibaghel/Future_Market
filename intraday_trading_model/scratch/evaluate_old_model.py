import sys
import os
import joblib
import pandas as pd
import numpy as np
from sklearn.metrics import classification_report, accuracy_score, precision_score, recall_score, f1_score
import pyarrow.parquet as pq

sys.path.append(".")

# Load models and scaler
print("Loading models...")
if os.path.exists("stacked_model.pkl") and os.path.exists("scaler.pkl"):
    stacked_model = joblib.load("stacked_model.pkl")
    scaler = joblib.load("scaler.pkl")
    print("Models loaded successfully!")
else:
    print("Error: Models or Scaler not found!")
    sys.exit(1)

# Recreate data loading to match batch_model.py
SYMBOLS = ["ASIANPAINT.NS", "AXISBANK.NS", "BAJFINANCE.NS", "BHARTIARTL.NS", "CIPLA.NS", "GRASIM.NS",
           "HCLTECH.NS", "HDFCAMC.NS", "INFY.NS", "ITC.NS", "KOTAKBANK.NS", "LT.NS", "MARUTI.NS",
           "M&M.NS", "NTPC.NS", "RELIANCE.NS", "SBIN.NS", "SUNPHARMA.NS", "TATASTEEL.NS", "TCS.NS",
           "TRIDENT.NS", "VOLTAS.NS", "WIPRO.NS", "ZOMATO.NS"]

def load_historical_data():
    return pd.concat([pq.read_table(f"historical/{sym}.parquet").to_pandas() for sym in SYMBOLS])

try:
    combined_data = load_historical_data()
    # Simple check of features
    # Note: we need features to evaluate. In batch_model.py, add_features does some engineering.
    # Let's inspect shape of scaler.pkl to see how many features it expects.
    print("Scaler features:", scaler.n_features_in_)
except Exception as e:
    print("Error loading data:", e)
