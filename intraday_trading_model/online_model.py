import joblib
import sqlite3
import pandas as pd
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import PassiveAggressiveClassifier
from river import linear_model, preprocessing, optim, compose
from datetime import datetime, timedelta
from stable_baselines3 import PPO
from gym import spaces
from sklearn.linear_model import SGDClassifier
from sklearn.utils.validation import check_is_fitted
import gym
from sklearn.preprocessing import LabelEncoder
import warnings
warnings.filterwarnings("ignore")


# ================================
# 🔹 RL Trading Environment
# ================================
class TradingEnv(gym.Env):
    def __init__(self, data, feature_calculator):
        super(TradingEnv, self).__init__()

        self.data = data
        self.feature_calculator = feature_calculator
        self.current_step = 0
        self.current_stock = None

        # Fetch feature names dynamically from FeatureCalculator
        sample_features = self.feature_calculator.compute_features(self.data[0])
        self.feature_keys = list(sample_features.keys()) if sample_features else []

        # Define action and observation space
        self.action_space = spaces.Discrete(3)  # 0=Hold, 1=Buy, 2=Sell
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(len(self.feature_keys),), dtype=np.float32
        )

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        self.current_stock = self.data[0].get("stock_code", None)

        features = self.feature_calculator.compute_features(self.data[0])
        self.state = self._get_feature_array(features)
        return np.array(self.state, dtype=np.float32), {}

    def step(self, action):
        terminated = False
        truncated = False

        reward = self._calculate_reward(action)

        if self.current_step < len(self.data) - 1:
            self.current_step += 1
            row = self.data[self.current_step]
            features = self.feature_calculator.compute_features(row)
            self.state = self._get_feature_array(features)
            self.current_stock = row.get("stock_code", None)

        if self.current_step >= len(self.data) - 1:
            terminated = True
        elif self.current_step >= 1000:
            truncated = True

        return (
            np.array(self.state, dtype=np.float32),
            reward,
            terminated,
            truncated,
            {}
        )

    def _calculate_reward(self, action):
        try:
            current_price = self.data[self.current_step]['close']
            next_price = self.data[self.current_step + 1]['close']

            if action == 1:  # Buy
                return next_price - current_price
            elif action == 2:  # Sell
                return current_price - next_price
            return 0  # Hold
        except IndexError:
            return 0

    def _get_feature_array(self, features):
        if not features:
            return np.zeros(len(self.feature_keys))
        return [features.get(key, 0) for key in self.feature_keys]


# ================================
# 🔹 EMA Class (Your Original Code)
# ================================
class EMA:
    def __init__(self, alpha):
        self.alpha = alpha
        self.value = None

    def update(self, new_value):
        if new_value is None:  # Handle None values
            return
        if self.value is None:
            self.value = new_value
        else:
            self.value = self.alpha * new_value + (1 - self.alpha) * self.value

    def get(self):
        return self.value


# ================================
# 🔹 Enhanced Feature Calculator (Your Code + My Additions)
# ================================
class FeatureCalculator:
    def __init__(self):
        self.returns_buffer = []
        self.volume_window = []
        self.ema_1440 = EMA(alpha=2 / (1440 + 1))
        self.close_prices = []
        self.high_prices = []
        self.low_prices = []
        self.vwap_data = []
        self.fourier_window = []
        self.order_flow = []

    def compute_features(self, new_data, is_historical=False):
        # Maintain buffers
        self.returns_buffer.append(new_data['close'])
        self.high_prices.append(new_data['high'])
        self.low_prices.append(new_data['low'])
        self.close_prices.append(new_data['close'])
        self.volume_window.append(new_data['volume'])
        self.fourier_window.append(new_data['close'])
        self.order_flow.append(new_data['volume'] * (new_data['close'] - new_data['open']))

        # Trim buffers
        for buffer in [self.returns_buffer, self.high_prices, self.low_prices,
                       self.close_prices, self.volume_window, self.fourier_window,
                       self.order_flow]:
            if len(buffer) > 50:
                buffer.pop(0)
        print(f"EMA_1440 Value: {self.ema_1440.get()}, Close Price: {new_data['close']}")

        print(f"Updating EMA with price: {new_data['close']}")
        self.ema_1440.update(new_data['close'])  # Ensure EMA is updated
        print(f"EMA_1440 After Update: {self.ema_1440.get()}")
        # print(f"Total EMA values stored: {len(self.ema_1440.value)}")
        if self.ema_1440.get() == 0:
            print("Not enough data for EMA_1440 calculation")
            return None  # Or some default value like previous close price

        # Your Original Features
        features = {
            'Returns_5m': self._calculate_returns_5m(),
            'Range': (new_data['high'] - new_data['low']) / new_data['close'],
            'Volume_Z': self._calculate_volume_zscore(),
            'EMA_1440': self.ema_1440.get(),
            'Regime': 1 if new_data['close'] > (self.ema_1440.get() or 0) else 0,
            'RSI': self.calculate_rsi(new_data['close']),
            'MACD': self.calculate_macd()[0],
            'Signal': self.calculate_macd()[1],
            'Bollinger_Upper': self.calculate_bollinger_bands()[0],
            'Bollinger_Lower': self.calculate_bollinger_bands()[1],
            'VWAP': self.calculate_vwap(new_data),
            'ATR': self.calculate_atr(),
            'Momentum': self.calculate_momentum(),
            'Stochastic_Oscillator': self.calculate_stochastic(),
            'ADX': self.calculate_adx(),
            'CCI': self.calculate_cci(),
            'Fourier_5m': np.fft.fft(self.fourier_window[-5:]).real.mean() if len(self.fourier_window) >= 5 else 0,
            'MACD_Histogram': self.calculate_macd()[0] - self.calculate_macd()[1],
            'Order_Flow': self.order_flow[-1] if self.order_flow else 0,
            'close': new_data['close']
        }
        # features = {f"Column_{i}": value for i, (key, value) in enumerate(features.items())}
        return features

    # Your Original Calculation Methods
    def _calculate_returns_5m(self):
        if len(self.returns_buffer) < 5:
            return 0.0
        return (self.returns_buffer[-1] - self.returns_buffer[0]) / self.returns_buffer[0]

    def _calculate_volume_zscore(self):
        if len(self.volume_window) < 2:
            return 0.0
        vol_mean = np.mean(self.volume_window)
        vol_std = np.std(self.volume_window)
        return (self.volume_window[-1] - vol_mean) / vol_std if vol_std != 0 else 0.0

    def calculate_rsi(self, close_price, period=14):
        if len(self.close_prices) < period:
            return 50
        closes = pd.Series(self.close_prices[-period:])
        delta = closes.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs.iloc[-1])) if not rs.isna().all() else 50

    def calculate_macd(self, short=12, long=26, signal=9):
        if len(self.close_prices) < long:
            return 0.0, 0.0
        closes = pd.Series(self.close_prices)
        short_ema = closes.ewm(span=short, adjust=False).mean()
        long_ema = closes.ewm(span=long, adjust=False).mean()
        macd = short_ema - long_ema
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        return macd.iloc[-1], signal_line.iloc[-1]

    def calculate_bollinger_bands(self, period=20, std_factor=2):
        if len(self.close_prices) < period:
            return 0.0, 0.0
        closes = pd.Series(self.close_prices)
        sma = closes.rolling(window=period).mean()
        std = closes.rolling(window=period).std()
        return sma.iloc[-1] + (std_factor * std.iloc[-1]), sma.iloc[-1] - (std_factor * std.iloc[-1])

    def calculate_vwap(self, new_data):
        self.vwap_data.append((new_data['close'], new_data['volume']))
        total_volume = sum(vol for _, vol in self.vwap_data)
        return sum(price * vol for price, vol in self.vwap_data) / total_volume if total_volume else new_data['close']

    def calculate_atr(self, period=14):
        if len(self.high_prices) < period:
            return 0.0
        high_low = np.array(self.high_prices) - np.array(self.low_prices)
        return pd.Series(high_low).rolling(window=period).mean().iloc[-1]

    def calculate_momentum(self, period=10):
        return self.close_prices[-1] - self.close_prices[-period] if len(self.close_prices) >= period else 0.0

    def calculate_stochastic(self, period=14):
        if len(self.close_prices) < period:
            return 50
        low_min = min(self.low_prices[-period:])
        high_max = max(self.high_prices[-period:])
        return ((self.close_prices[-1] - low_min) / (high_max - low_min)) * 100

    def calculate_adx(self, period=14):
        return np.mean(np.abs(np.diff(self.high_prices[-period:]))) if len(self.high_prices) >= period else 0.0

    def calculate_cci(self, period=14):
        if len(self.close_prices) < period:
            return 0.0
        tp = (np.array(self.high_prices[-period:]) + np.array(self.low_prices[-period:]) + np.array(
            self.close_prices[-period:])) / 3
        return (tp[-1] - np.mean(tp)) / (0.015 * np.std(tp))


# ================================
# 🔹 Hybrid Trader (Your Code + RL + Risk)
# ================================
class HybridTrader:
    def __init__(self):
        # Your Original Components
        self.stacked_model = joblib.load("stacked_model.pkl")
        self.scaler = joblib.load("scaler.pkl")  # Load trained scaler
        self.online_model = Pipeline([
            ("scaler", self.scaler),  # ✅ Use the loaded scaler
            ("classifier", SGDClassifier(loss='log_loss'))
        ])

        self.batch_score = 1.0
        self.online_score = 1.0

        # My Additions
        self.rl_agent = PPO.load("trading_ppo")  # Pre-trained model
        self.meta_model = PassiveAggressiveClassifier()  # False signal filter
        self.risk_manager = self.RiskManager()
        self.trade_history = []
        self.window_size = 100
        self.positions = set()

        self.label_encoder = LabelEncoder()
        self.sector_map = {
            "ASIANPAINT.NS": "Paints",
            "AXISBANK.NS": "Banking",
            "BAJFINANCE.NS": "Finance",
            "BHARTIARTL.NS": "Telecom",
            "CIPLA.NS": "Pharmaceuticals",
            "GRASIM.NS": "Cement",
            "HCLTECH.NS": "IT",
            "HDFCAMC.NS": "Finance",
            "INFY.NS": "IT",
            "ITC.NS": "FMCG",
            "KOTAKBANK.NS": "Banking",
            "LT.NS": "Infrastructure",
            "MARUTI.NS": "Automobile",
            "M&M.NS": "Automobile",
            "NTPC.NS": "Energy",
            "RELIANCE.NS": "Energy",
            "SBIN.NS": "Banking",
            "SUNPHARMA.NS": "Pharmaceuticals",
            "TATASTEEL.NS": "Steel",
            "TCS.NS": "IT",
            "TRIDENT.NS": "Textile",
            "VOLTAS.NS": "Consumer Durables",
            "WIPRO.NS": "IT",
            "ZOMATO.NS": "Food Delivery"
        }
        self.label_encoder.fit(list(self.sector_map.keys()))

        self.sector_limits = {  # ✅ Initialize sector limits to fix AttributeError
            "Paints": 0.3,
            "Banking": 0.4,
            "Finance": 0.35,
            "Telecom": 0.25,
            "Pharmaceuticals": 0.3,
            "Cement": 0.2,
            "IT": 0.5,
            "FMCG": 0.3,
            "Infrastructure": 0.25,
            "Automobile": 0.35,
            "Energy": 0.4,
            "Steel": 0.3,
            "Textile": 0.2,
            "Consumer Durables": 0.3,
            "Food Delivery": 0.25
        }
        self.sector_map = {
            "ASIANPAINT.NS": "Paints",
            "AXISBANK.NS": "Banking",
            "BAJFINANCE.NS": "Finance",
            "BHARTIARTL.NS": "Telecom",
            "CIPLA.NS": "Pharmaceuticals",
            "GRASIM.NS": "Cement",
            "HCLTECH.NS": "IT",
            "HDFCAMC.NS": "Finance",
            "INFY.NS": "IT",
            "ITC.NS": "FMCG",
            "KOTAKBANK.NS": "Banking",
            "LT.NS": "Infrastructure",
            "MARUTI.NS": "Automobile",
            "M&M.NS": "Automobile",
            "NTPC.NS": "Energy",
            "RELIANCE.NS": "Energy",
            "SBIN.NS": "Banking",
            "SUNPHARMA.NS": "Pharmaceuticals",
            "TATASTEEL.NS": "Steel",
            "TCS.NS": "IT",
            "TRIDENT.NS": "Textile",
            "VOLTAS.NS": "Consumer Durables",
            "WIPRO.NS": "IT",
            "ZOMATO.NS": "Food Delivery"
        }
        self.feature_columns = [
            'Returns_5m', 'Range', 'Volume_Z', 'EMA_1440', 'Regime', 'RSI', 'MACD', 'Signal',
            'Bollinger_Upper', 'Bollinger_Lower', 'VWAP', 'ATR', 'Momentum', 'Stochastic_Oscillator',
            'ADX', 'CCI', 'Fourier_5m', 'MACD_Histogram', 'Order_Flow','Symbol_Encoded'
        ]


    class RiskManager:
        def __init__(self):
            self.atr = 1.5
            self.kelly = 0.5
            self.profit_factor = 1.0

        def update_profit_factor(self, wins, losses):
            """Profit factor calculation: ratio of gross profits to gross losses"""
            self.profit_factor = (wins / max(1, losses)) if losses > 0 else 1.0

        def update(self, features):
            self.atr = features['ATR']
            # Simplified Kelly: Adjust based on your win rate
            self.kelly = 0.5 * (0.6 - (1 - 0.6) / 2)  # 60% win rate assumed

        # 🔄 Dynamic Threshold Adjustment

    def _get_dynamic_threshold(self, volatility):
        """ Adjusts threshold based on market volatility """
        base_threshold = 0.6
        sensitivity = 0.3  # How much volatility affects threshold
        return base_threshold + (volatility * sensitivity)

        # 🔄 Adaptive Kelly Calculation
    def _calculate_kelly(self):
        """ Uses rolling window win rate """
        if len(self.trade_history) < 10:  # Minimum trades
            return 0.5  # Default

        win_rate = np.mean(self.trade_history[-self.window_size:])
        loss_rate = 1 - win_rate
        profit_factor = getattr(self.risk_manager, "profit_factor", 1.0)  # ✅ Default value if missing
        return win_rate - (loss_rate / max(1, profit_factor))

    def _sector_exposure(self, symbol):
        sector = self.sector_map.get(symbol, "Unknown")
        total_positions = len(self.positions) if len(self.positions) > 0 else 1  # Prevent division by zero
        current_exposure = sum(1 for sym in self.positions if self.sector_map.get(sym) == sector) / total_positions
        return min(1.0, current_exposure / self.sector_limits.get(sector, 0.5))

    def update_weights(self, batch_correct, online_correct):
        alpha = 0.05
        self.batch_score = (1 - alpha) * self.batch_score + alpha * batch_correct
        self.online_score = (1 - alpha) * self.online_score + alpha * online_correct

    def predict_and_learn(self, features, symbol, target=None):
        print(f"📊 Predicting for {symbol} with features: {features}")

        # print("Model Features:", self.stacked_model.feature_names_in_)  # Expected features
        # print("Input Features:", list(features.keys()))

        # Convert features to array
        features_array = np.array([features])

        try:
            check_is_fitted(self.online_model)
        except:
            print("⚠️ Online model is not fitted. Training before prediction...")
            if hasattr(self.online_model.steps[-1][1], 'partial_fit'):  # 🛠 Fix: Get last step model
                self.online_model.steps[-1][1].partial_fit(features_array, [0], classes=np.array([0, 1]))
            else:
                print("⚠️ Online model does not support partial fitting!")

        # Get predictions

        if not isinstance(features, dict):
            return None

        if symbol not in self.label_encoder.classes_:
            print(f"⚠️ Warning: Symbol {symbol} not recognized. Defaulting to 0.")
            symbol_encoded = 0
        else:
            symbol_encoded = self.label_encoder.transform([symbol])[0]

        features['Symbol_Encoded'] = symbol_encoded

        features_array = np.array(list(features.values()), dtype=float).reshape(1, -1)


        stacked_prob = self.stacked_model.predict_proba(features_array)[0][1]
        online_prob = self.online_model.predict_proba(features_array)[0][1]
        rl_action, _ = self.rl_agent.predict(features_array)
        try:
            meta_prob = self.meta_model.predict_proba_one(features)
        except AttributeError:
            meta_prob = {1: 0.5}

        # Combine predictions
        final_prob = (
                0.4 * stacked_prob +
                0.3 * online_prob +
                0.2 * meta_prob.get(1, 0.5) +
                0.1 * (1 if rl_action == 1 else 0)
        )

        features_dict = dict(zip(features_df.columns, features_df.values[0]))
        volatility = features_dict.get('Volatility', 0.05)

        buy_threshold = self._get_dynamic_threshold(volatility)
        sell_threshold = 1 - buy_threshold
        self.risk_manager.kelly = self._calculate_kelly()
        sector_exposure = self._sector_exposure(symbol)
        position_size = self.risk_manager.kelly * 100 * max(0, 1 - sector_exposure)

        if isinstance(features, np.ndarray):
            features = dict(zip(self.feature_columns, features))
        # Risk management

        # Fix for 'close' missing
        if "close" not in features:
            print("⚠️ Warning: 'close' price missing in features. Using last available close price.")
            if self.trade_history and isinstance(self.trade_history[-1], dict) and "close" in self.trade_history[-1]:
                features["close"] = self.trade_history[-1]["close"]
            else:
                features["close"] = 100.0  # Default value set kar rahe hain

            # Ab safely features["close"] ko access kar sakte ho
        stop_loss = features["close"] - (2 * self.risk_manager.atr)

        # Removing position safely
        if symbol in self.positions:
            self.positions.remove(symbol)

        # Trading decision
        if final_prob > buy_threshold and sector_exposure < 0.3:
            self.positions.add(symbol)
            print(f"🚀 BUY {position_size:.2f}% ({symbol})")
        elif final_prob < sell_threshold:
            self.positions.discard(symbol)
            print(f"🔻 SELL {position_size:.2f}% ({symbol})")

        X = np.array([list(features.values())])  # Convert dictionary values into numpy array

        expected_features = self.online_model.named_steps["classifier"].coef_.shape[1]

        if X.shape[1] > expected_features:
            X = X[:, :expected_features]  # Trim extra features
        elif X.shape[1] < expected_features:
            print(f"⚠️ Warning: Feature mismatch! Expected {expected_features}, but got {X.shape[1]}.")
            return None  # Stop execution to prevent error
        # Online learning
        if target is not None:
            self.online_model.named_steps["classifier"].partial_fit(X, [target])
            self.meta_model.partial_fit(
                np.array([list(features.values())]),  # Convert dictionary to numpy array
                [int(final_prob > 0.5)],
                classes=[0, 1]  # Ensure binary classification
            )
            batch_correct = int((stacked_prob > 0.5) == target)
            online_correct = int((online_prob > 0.5) == target)
            self.update_weights(batch_correct, online_correct)
            self.trade_history.append(1 if (final_prob > 0.5) == target else 0)
            self.trade_history = self.trade_history[-self.window_size:]

        return final_prob


# ================================
# 🔹 Data Fetching & Main Loop (Your Original Code)
# ================================
def fetch_latest_data(symbol):
    with sqlite3.connect("intraday.db") as conn:
        query = f"SELECT * FROM '{symbol.replace('.', '_')}' ORDER BY datetime DESC LIMIT 100"
        df = pd.read_sql(query, conn)
    return df.to_dict("records")


SYMBOLS = ["ASIANPAINT.NS", "AXISBANK.NS", "BAJFINANCE.NS", "BHARTIARTL.NS", "CIPLA.NS", "GRASIM.NS",
           "HCLTECH.NS", "HDFCAMC.NS", "INFY.NS", "ITC.NS", "KOTAKBANK.NS", "LT.NS", "MARUTI.NS",
           "M&M.NS", "NTPC.NS", "RELIANCE.NS", "SBIN.NS", "SUNPHARMA.NS", "TATASTEEL.NS", "TCS.NS",
           "TRIDENT.NS", "VOLTAS.NS", "WIPRO.NS", "ZOMATO.NS"]

if __name__ == "__main__":
    trader = HybridTrader()
    feature_calc = FeatureCalculator()

    for symbol in SYMBOLS:
        print(f"⚡ Processing {symbol}...")
        market_data = fetch_latest_data(symbol)
        prev_close = None

        for row in market_data:
            features = feature_calc.compute_features(row)
            current_close = row['close']

            if prev_close is not None:
                target = 1 if current_close > prev_close * 1.005 else 0
                print(f"🛠 Calling predict_and_learn with symbol={symbol}, target={target}")
                features_without_symbol = {key: value for key, value in features.items() if key != 'symbol'}
                features_df = pd.DataFrame([features])
                if features is not None:
                    prediction = trader.predict_and_learn(features_df.values[0], symbol, target)
                else:
                    print(f"⚠️ Skipping {symbol}, features not computed!")

            prev_close = current_close