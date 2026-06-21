from stable_baselines3 import PPO
from online_model import TradingEnv
import pandas as pd
import pyarrow.parquet as pq
import os
import warnings
from online_model import TradingEnv, FeatureCalculator

warnings.filterwarnings("ignore")

# ✅ SYMBOL LIST (Jo stocks ka data fetch karna hai)
SYMBOLS = ["ASIANPAINT.NS", "AXISBANK.NS", "BAJFINANCE.NS", "BHARTIARTL.NS", "CIPLA.NS", "GRASIM.NS",
           "HCLTECH.NS", "HDFCAMC.NS", "INFY.NS", "ITC.NS", "KOTAKBANK.NS", "LT.NS", "MARUTI.NS",
           "M&M.NS", "NTPC.NS", "RELIANCE.NS", "SBIN.NS", "SUNPHARMA.NS", "TATASTEEL.NS", "TCS.NS",
           "TRIDENT.NS", "VOLTAS.NS", "WIPRO.NS", "ZOMATO.NS"]


# ✅ Function to Load Historical Data Efficiently
def load_historical_data():
    print("📥 Loading historical data...")
    data_frames = []

    for sym in SYMBOLS:
        file_path = f"historical/{sym}.parquet"
        if os.path.exists(file_path):  # ✅ Check if file exists
            df = pq.read_table(file_path).to_pandas()
            df["symbol"] = sym  # ✅ Add symbol column for tracking
            data_frames.append(df)
        else:
            print(f"⚠️ Warning: Data for {sym} not found!")

    if not data_frames:
        raise FileNotFoundError("❌ No historical data found. Please check your files.")

    return pd.concat(data_frames, ignore_index=True)


# ✅ Load Historical Data
historical_data = load_historical_data().to_dict("records")

feature_calculator = FeatureCalculator()

# ✅ Create Environment
env = TradingEnv(historical_data, feature_calculator)

# ✅ Train PPO Model
print("🚀 Training PPO model...")
model = PPO('MlpPolicy', env, verbose=1)
model.learn(total_timesteps=10000)

# ✅ Save the Model
model.save("trading_ppo")
print("✅ Model saved successfully as 'trading_ppo'.")
