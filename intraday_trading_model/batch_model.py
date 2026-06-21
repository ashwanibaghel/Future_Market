import sqlite3
import pandas as pd
import lightgbm as lgb
import xgboost as xgb
import joblib
import numpy as np
from skopt import BayesSearchCV
from sklearn.ensemble import StackingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
import talib
from hmmlearn import hmm
from catboost import CatBoostClassifier
import pyarrow.parquet as pq
import warnings
warnings.filterwarnings("ignore")

SYMBOLS = ["ASIANPAINT.NS", "AXISBANK.NS", "BAJFINANCE.NS", "BHARTIARTL.NS", "CIPLA.NS", "GRASIM.NS",
           "HCLTECH.NS", "HDFCAMC.NS", "INFY.NS", "ITC.NS", "KOTAKBANK.NS", "LT.NS", "MARUTI.NS",
           "M&M.NS", "NTPC.NS", "RELIANCE.NS", "SBIN.NS", "SUNPHARMA.NS", "TATASTEEL.NS", "TCS.NS",
           "TRIDENT.NS", "VOLTAS.NS", "WIPRO.NS", "ZOMATO.NS"]


def load_data():
    print("Loading realtime data...")
    conn = sqlite3.connect('intraday.db')
    dfs = [pd.read_sql(f'SELECT * FROM "{sym.replace(".", "_")}"', conn) for sym in SYMBOLS]
    conn.close()
    return pd.concat(dfs)


def load_historical_data():
    print("Loading historical data...")
    return pd.concat([pq.read_table(f"historical/{sym}.parquet").to_pandas() for sym in SYMBOLS])


def add_features(df):
    # Original features
    df['Returns_30m'] = df['close'].pct_change(30)
    df['Volatility'] = df['close'].pct_change().rolling(20).std()
    df['Momentum'] = df['close'] - df['close'].rolling(14).mean()
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['close'].ewm(span=200, adjust=False).mean()
    df['RSI'] = talib.RSI(df['close'], timeperiod=14)
    macd, macdsignal, _ = talib.MACD(df['close'])
    df['MACD'] = macd - macdsignal
    df['VWAP'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
    upper, middle, lower = talib.BBANDS(df['close'], timeperiod=20)
    df['Bollinger_Up'] = upper
    df['Bollinger_Down'] = lower
    df['Trend'] = (df['EMA_50'] > df['EMA_200']).astype(int)

    # New features
    df['Fourier_5m'] = np.fft.fft(df['close'].values)[1].real
    df['Order_Flow'] = df['volume'] * (df['close'] - df['open'])
    hmm_model = hmm.GaussianHMM(n_components=3)
    hmm_model.fit(df[['close']].values.reshape(-1, 1))
    df['Market_Regime'] = hmm_model.predict(df[['close']].values.reshape(-1, 1))

    # Save HMM model
    joblib.dump(hmm_model, "hmm_model.pkl")

    return df.dropna()


if __name__ == "__main__":
    # Load and process data
    print("Starting model training...")
    historical_data = load_historical_data()
    realtime_data = load_data()

    # Feature engineering
    historical_data = add_features(historical_data)
    realtime_data = add_features(realtime_data)
    combined_data = pd.concat([historical_data, realtime_data])
    combined_data['target'] = (combined_data['close'].shift(-5) > combined_data['close'] * 1.005).astype(int)

    # Prepare features
    X = combined_data.drop(columns=['target', 'datetime'])
    y = combined_data['target']
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0)

    # Train/test split
    train_size = int(len(X) * 0.8)
    X_train, X_test = X[:train_size], X[train_size:]
    y_train, y_test = y[:train_size], y[train_size:]

    # Feature scaling
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)
    joblib.dump(scaler, "scaler.pkl")

    # Bayesian Optimization for Models
    print("Optimizing LightGBM...")
    lgb_opt = BayesSearchCV(lgb.LGBMClassifier(),
                            {'num_leaves': (20, 50), 'learning_rate': (0.005, 0.05, 'log-uniform'),
                             'feature_fraction': (0.5, 1.0), 'bagging_fraction': (0.5, 1.0)},
                            n_iter=30, cv=3)
    lgb_opt.fit(X_train, y_train)

    print("Optimizing XGBoost...")
    xgb_opt = BayesSearchCV(xgb.XGBClassifier(eval_metric="logloss"),
                            {'max_depth': (3, 10), 'learning_rate': (0.01, 0.3)}, n_iter=30, cv=3)
    xgb_opt.fit(X_train, y_train)

    print("Optimizing CatBoost...")
    cat_opt = BayesSearchCV(CatBoostClassifier(verbose=0),
                            {'depth': (3, 10), 'learning_rate': (0.01, 0.3)}, n_iter=30, cv=3)
    cat_opt.fit(X_train, y_train)

    # Create stacked model
    print("Training stacked model...")
    stacked_model = StackingClassifier(
        estimators=[
            ('lightgbm', lgb_opt.best_estimator_),
            ('xgboost', xgb_opt.best_estimator_),
            ('catboost', cat_opt.best_estimator_)
        ],
        final_estimator=LogisticRegression()
    )
    stacked_model.fit(X_train, y_train)

    # Save models
    joblib.dump(stacked_model, "stacked_model.pkl")
    print("Model training complete!")