import os
from dotenv import load_dotenv

load_dotenv()

CAPITAL_API_KEY    = os.getenv("CAPITAL_API_KEY", "")
CAPITAL_EMAIL      = os.getenv("CAPITAL_EMAIL", "")
CAPITAL_PASSWORD   = os.getenv("CAPITAL_PASSWORD", "")
CAPITAL_ENV        = os.getenv("CAPITAL_ENV", "demo")
CAPITAL_ACCOUNT_ID = os.getenv("CAPITAL_ACCOUNT_ID", "")

# Capital.com API base URLs differ by environment.
_BASE_URLS = {
    "demo": "https://demo-api-capital.backend-capital.com/api/v1",
    "live": "https://api-capital.backend-capital.com/api/v1",
}
API_URL = _BASE_URLS.get(CAPITAL_ENV, _BASE_URLS["demo"])

# ── All pairs traded simultaneously ─────────────────────────────────────────
# Override via env: SYMBOLS=EURUSD,GBPUSD,GOLD
_default_symbols = (
    "EURUSD,GBPUSD,AUDUSD,NZDUSD,"
    "USDCAD,USDCHF,"
    "USDJPY,EURJPY,GBPJPY,"
    "GOLD,"
    "US100,US30"
)
SYMBOLS: list[str] = os.getenv("SYMBOLS", _default_symbols).split(",")

TIMEFRAME        = os.getenv("TIMEFRAME", "HOUR")
RISK_PER_TRADE   = float(os.getenv("RISK_PER_TRADE",   "0.01"))
DAILY_LOSS_LIMIT = float(os.getenv("DAILY_LOSS_LIMIT", "0.03"))

# 0 = unlimited across all pairs combined (strategy quality is the gate)
MAX_TRADES_PER_DAY = int(os.getenv("MAX_TRADES_PER_DAY", "0"))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

# Enough candles to fully converge EMA200
CANDLE_COUNT  = 300

# Main loop interval in seconds (1 hour)
LOOP_INTERVAL = 3600

# ── Pip size: value of 1 pip for 1 unit in account currency ─────────────────
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
    "GOLD":   0.1,
    "US100":  1.0,
    "US30":   1.0,
}

# ── Per-symbol stop-loss and take-profit in pips ─────────────────────────────
# Indices and Gold need wider stops than FX majors.
# Take-profit is always 2× stop (1:2 risk-reward).
SL_PIPS: dict[str, int] = {
    "EURUSD": 20,  "GBPUSD": 20,  "AUDUSD": 20,  "NZDUSD": 20,
    "USDCAD": 20,  "USDCHF": 20,
    "USDJPY": 20,  "EURJPY": 25,  "GBPJPY": 25,
    "GOLD":   200,              # Gold: $20 move at 0.1/pip
    "US100":  50,  "US30":   50, # Index points
}
TP_PIPS: dict[str, int] = {k: v * 2 for k, v in SL_PIPS.items()}

# Fallback defaults if a symbol isn't in the dicts above
DEFAULT_SL_PIPS = 20
DEFAULT_TP_PIPS = 40
