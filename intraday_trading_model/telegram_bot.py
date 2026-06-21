import time
from datetime import datetime
import telegram
from online_model import HybridTrader, FeatureCalculator, fetch_latest_data  # Updated modules
import warnings
warnings.filterwarnings("ignore")

# Telegram bot setup
API_KEY = '7957647696:AAHilKkUYaekme6B55ghPinWBgexZ9TnJaA'
CHAT_ID = '454223593,936921214'
bot = telegram.Bot(token=API_KEY)

# Trading settings (Dynamic thresholds now)
RISK_THRESHOLD = 0.65  # Base threshold (adjusted by volatility)

SYMBOLS = ["ASIANPAINT.NS", "AXISBANK.NS", "BAJFINANCE.NS", "BHARTIARTL.NS", "CIPLA.NS", "GRASIM.NS",
    "HCLTECH.NS", "HDFCAMC.NS", "INFY.NS", "ITC.NS", "KOTAKBANK.NS", "LT.NS", "MARUTI.NS",
    "M&M.NS", "NTPC.NS", "RELIANCE.NS", "SBIN.NS", "SUNPHARMA.NS", "TATASTEEL.NS", "TCS.NS",
    "TRIDENT.NS", "VOLTAS.NS", "WIPRO.NS", "ZOMATO.NS"]

# Initialize components
trader = HybridTrader()
feature_calc = FeatureCalculator()


# Real-Time Monitor (Updated for ATR-based SL)
class RealTimeMonitor:
    def __init__(self):
        self.positions = {}  # {symbol: {'entry_price': X, 'atr': Y, 'size': Z}}

        # Symbol Mapping
        self.symbol_map = {
            "ASIANPAINT.NS": 1, "AXISBANK.NS": 2, "BAJFINANCE.NS": 3, "BHARTIARTL.NS": 4,
            "CIPLA.NS": 5, "GRASIM.NS": 6, "HCLTECH.NS": 7, "HDFCAMC.NS": 8,
            "INFY.NS": 9, "ITC.NS": 10, "KOTAKBANK.NS": 11, "LT.NS": 12,
            "MARUTI.NS": 13, "M&M.NS": 14, "NTPC.NS": 15, "RELIANCE.NS": 16,
            "SBIN.NS": 17, "SUNPHARMA.NS": 18, "TATASTEEL.NS": 19, "TCS.NS": 20,
            "TRIDENT.NS": 21, "VOLTAS.NS": 22, "WIPRO.NS": 23, "ZOMATO.NS": 24
        }

    def update_position(self, symbol, entry_price, atr, size):
        self.positions[symbol] = {
            'entry_price': entry_price,
            'atr': atr,
            'size': size  # Kelly-based position size
        }

    def check_exit_conditions(self, symbol, current_price):
        if symbol not in self.positions:
            return None

        position = self.positions[symbol]
        atr_sl = 2 * position['atr']
        sl_price = position['entry_price'] - atr_sl
        target_price = position['entry_price'] + (1.5 * atr_sl)

        if current_price <= sl_price:
            return "STOP_LOSS"
        elif current_price >= target_price:
            return "TAKE_PROFIT"
        return None


# Initialize
monitor = RealTimeMonitor()

# Main Loop with New Features
while True:
    for symbol in SYMBOLS:
        try:
            market_data = fetch_latest_data(symbol)
            if market_data is None or len(market_data) == 0:
                print(f"No data for {symbol}, skipping this symbol.")
                continue
            for row in market_data:
                features = feature_calc.compute_features(row, symbol)
                current_price = row['close']

                # Check if symbol is in the mapping
                if symbol in monitor.symbol_map:
                    mapped_symbol = monitor.symbol_map[symbol]
                else:
                    mapped_symbol = 0  # Default value for unknown symbols
                    print(f"⚠️ Warning: {symbol} not found in symbol_map!")

                prediction = trader.predict_and_learn(mapped_symbol, features, target=None)

                volatility = features['Volatility']
                dynamic_threshold = RISK_THRESHOLD + (volatility * 0.5)

                if prediction > dynamic_threshold:
                    sl = current_price - (2 * features['ATR'])
                    size = trader.risk_manager.kelly * 100

                    monitor.update_position(
                        symbol=symbol,
                        entry_price=current_price,
                        atr=features['ATR'],
                        size=size
                    )

                    msg = f"""🚀 **BUY** {symbol} (Mapped: {mapped_symbol})\n
Price: {current_price:.2f}\nSize: {size:.2f}%\nSL: {sl:.2f} (ATR: {features['ATR']:.2f})\nConfidence: {prediction:.2f}%"""
                    bot.send_message(chat_id=CHAT_ID, text=msg)

                exit_signal = monitor.check_exit_conditions(symbol, current_price)
                if exit_signal:
                    pnl = ((current_price - monitor.positions[symbol]['entry_price']) /
                           monitor.positions[symbol]['entry_price']) * 100
                    msg = f"""⚠️ **{exit_signal}** {symbol}\n
Entry: {monitor.positions[symbol]['entry_price']:.2f}\nExit: {current_price:.2f}\nPnL: {pnl:.2f}%"""
                    bot.send_message(chat_id=CHAT_ID, text=msg)
                    del monitor.positions[symbol]

        except Exception as e:
            print(f"Error processing {symbol}: {str(e)}")

    if 9 < datetime.now().hour < 15:
        time.sleep(60)
    else:
        time.sleep(300)
