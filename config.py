import os
from dotenv import load_dotenv

load_dotenv()

CAPITAL_API_KEY = os.getenv("CAPITAL_API_KEY", "")
CAPITAL_EMAIL = os.getenv("CAPITAL_EMAIL", "")
CAPITAL_PASSWORD = os.getenv("CAPITAL_PASSWORD", "")
CAPITAL_ENV = os.getenv("CAPITAL_ENV", "demo")

_BASE_URLS = {
    "demo": "https://demo-api.capital.com/api/v1",
    "live": "https://api.capital.com/api/v1",
}
API_URL = _BASE_URLS.get(CAPITAL_ENV, _BASE_URLS["demo"])

SYMBOL = os.getenv("SYMBOL", "EURUSD")
TIMEFRAME = os.getenv("TIMEFRAME", "HOUR")
RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "0.01"))
STOP_LOSS_PIPS = int(os.getenv("STOP_LOSS_PIPS", "20"))
TAKE_PROFIT_PIPS = int(os.getenv("TAKE_PROFIT_PIPS", "40"))
# 0 = unlimited (strategy quality is the only filter)
MAX_TRADES_PER_DAY = int(os.getenv("MAX_TRADES_PER_DAY", "0"))
DAILY_LOSS_LIMIT = float(os.getenv("DAILY_LOSS_LIMIT", "0.03"))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Enough candles to fully converge EMA200
CANDLE_COUNT = 300

# Main loop interval in seconds (1 hour)
LOOP_INTERVAL = 3600

# Pip size per instrument (value of 1 pip for 1 unit in account currency)
PIP_SIZES: dict[str, float] = {
    "EURUSD": 0.0001,
    "GBPUSD": 0.0001,
    "AUDUSD": 0.0001,
    "NZDUSD": 0.0001,
    "USDCAD": 0.0001,
    "USDCHF": 0.0001,
    "USDJPY": 0.01,
    "EURJPY": 0.01,
    "GBPJPY": 0.01,
    "XAUUSD": 0.1,
    "US100": 1.0,
    "US30":  1.0,
}
