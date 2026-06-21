import os
import sqlite3
import pandas as pd
import yfinance as yf
import fastparquet as pq
from datetime import datetime, timedelta
import schedule
import time
import warnings
warnings.filterwarnings("ignore")


def initialize_database():
    """Delete existing tables in intraday.db (only once) before starting updates."""
    with sqlite3.connect('intraday.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        for table in tables:
            cursor.execute(f"DROP TABLE IF EXISTS '{table[0]}';")
        conn.commit()
    print("Database initialized. All old tables deleted.")


# ✅ 30-Minute Aggregated Historical Data
def aggregate_to_30min(file_path, symbol):
    """Read 1-minute historical data, aggregate to 30-minute intervals, and save as Parquet."""
    try:
        print(f"Processing historical data for {symbol}...")
        df = pd.read_csv(file_path)
        df['datetime'] = pd.to_datetime(df['date'])
        df.set_index('datetime', inplace=True)

        # 30-minute resampling
        df_30m = df.resample('30min').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()

        os.makedirs("historical", exist_ok=True)  # Ensure folder exists

        parquet_path = f"historical/{symbol}.parquet"
        df_30m.to_parquet(parquet_path, engine='fastparquet', compression='zstd')
        print(f"✅ 30-minute aggregated data saved for {symbol} in {parquet_path}")
    except Exception as e:
        print(f"❌ Error processing historical data for {symbol}: {e}")


# ✅ Fetch & Update Historical Data (Every 30 Minutes)
def fetch_and_update_daily(symbol):
    """Fetch 30-minute historical data and update the existing Parquet file."""
    try:
        print(f"Fetching 30-minute historical data for {symbol}...")
        df_new = yf.download(symbol, period="1d", interval="30m")
        df_new = df_new[['Open', 'High', 'Low', 'Close', 'Volume']]
        df_new.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'},
                      inplace=True)
        df_new.index.name = 'datetime'
        df_new.reset_index(inplace=True)

        parquet_path = f"historical/{symbol}.parquet"

        if os.path.exists(parquet_path):
            df_existing = pd.read_parquet(parquet_path)
            df_existing['datetime'] = pd.to_datetime(df_existing['date'])
            df_existing.set_index('datetime', inplace=True)
        else:
            print(f"⚠ No existing Parquet file found for {symbol}, creating new one.")
            df_existing = pd.DataFrame()

        # Merge the new data with existing data
        df_new['datetime'] = pd.to_datetime(df_new['date'])
        df_new.set_index('datetime', inplace=True)
        df_combined = pd.concat([df_existing, df_new]).sort_index().drop_duplicates()

        # Save combined data with company name
        df_combined.to_parquet(parquet_path, engine='fastparquet', compression='zstd')
        print(f"✅ {symbol} historical data updated in {parquet_path}")
    except Exception as e:
        print(f"❌ Error updating historical data for {symbol}: {e}")


# ✅ Save Real-Time Data to SQLite (Every 10 Minutes)
import sqlite3
import pandas as pd
import yfinance as yf

def save_realtime_to_db(symbol, df):
    """Save real-time data to intraday.db with correct column names and table name fix."""
    try:
        print(f"Saving real-time data for {symbol} to intraday.db...")

        conn = sqlite3.connect("intraday.db")

        # ✅ Ensure correct column names
        df.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']  # Fix column names

        # ✅ Convert datetime to string (SQLite doesn't support native datetime type)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df['datetime'] = df['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')

        # ✅ Fix table name (replace `.` with `_`)
        table_name = symbol.replace(".", "_")

        # ✅ Save data to SQLite with correct schema
        df.to_sql(table_name, conn, if_exists="replace", index=False,
                  dtype={
                      'datetime': 'TEXT',
                      'open': 'REAL',
                      'high': 'REAL',
                      'low': 'REAL',
                      'close': 'REAL',
                      'volume': 'INTEGER'
                  })

        conn.close()
        print(f"✅ Real-time data for {symbol} saved as {table_name} in intraday.db")

    except Exception as e:
        print(f"❌ Error saving real-time data for {symbol} to intraday.db: {e}")

# ✅ Fetch & Save Real-Time Data
def fetch_and_save_realtime(symbol):
    """Fetch real-time data (1-minute interval) and save to intraday.db."""
    try:
        print(f"Fetching real-time data for {symbol}...")
        df_realtime = yf.download(symbol, period="2d", interval="1m")

        time.sleep(2)
        # ✅ Select & Rename Columns Properly
        df_realtime = df_realtime[['Open', 'High', 'Low', 'Close', 'Volume']]
        df_realtime.index.name = 'datetime'
        df_realtime.reset_index(inplace=True)
        df_realtime.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']  # Fix column names

        save_realtime_to_db(symbol, df_realtime)
    except Exception as e:
        print(f"❌ Error fetching real-time data for {symbol}: {e}")

# ✅ Process Historical Data (One-time setup)
def process_historical_data():
    """Process all historical data files in the data folder."""
    data_folder = "data"
    for file_name in os.listdir(data_folder):
        if file_name.endswith(".csv"):
            symbol = os.path.splitext(file_name)[0]  # Extract symbol
            file_path = os.path.join(data_folder, file_name)
            aggregate_to_30min(file_path, symbol)


# ✅ Schedule Daily Updates (Historical every 30 min, Real-time every 10 min)
def schedule_updates():
    """Schedule automatic updates for historical and real-time data."""
    for symbol in symbols:
        fetch_and_save_realtime(symbol)
        schedule.every().day.at("00:15").do(fetch_and_update_daily, symbol=symbol)
        schedule.every(10).minutes.do(fetch_and_save_realtime, symbol=symbol)

    print("📅 Scheduler started for real-time and historical updates...")
    while True:
        schedule.run_pending()
        time.sleep(1)


# 🔥 List of Company Symbols (NSE Stocks)
symbols = [
    "ASIANPAINT.NS", "AXISBANK.NS", "BAJFINANCE.NS", "BHARTIARTL.NS", "CIPLA.NS", "GRASIM.NS",
    "HCLTECH.NS", "HDFCAMC.NS", "INFY.NS", "ITC.NS", "KOTAKBANK.NS", "LT.NS", "MARUTI.NS",
    "M&M.NS", "NTPC.NS", "RELIANCE.NS", "SBIN.NS", "SUNPHARMA.NS", "TATASTEEL.NS", "TCS.NS",
    "TRIDENT.NS", "VOLTAS.NS", "WIPRO.NS", "ZOMATO.NS"
]

# initialize_database()

# ✅ Step 1: Process Historical Data (Run Once)
process_historical_data()

# ✅ Step 2: Start Scheduler for Daily Updates
schedule_updates()
