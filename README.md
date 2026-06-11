# Forex Strategy Bot — Capital.com

Automated trading bot for Capital.com using an **EMA50 / EMA200 + RSI pullback** strategy on the H1 chart.

## Strategy

| Condition | BUY | SELL |
|-----------|-----|------|
| Trend filter | Price & EMA50 above EMA200 | Price & EMA50 below EMA200 |
| Entry trigger | RSI 45–60 (pullback in uptrend) | RSI 40–55 (pullback in downtrend) |
| Stop loss | 20 pips | 20 pips |
| Take profit | 40 pips (1 : 2 RR) | 40 pips |

## Features

- Dynamic position sizing (1 % account risk per trade)
- Daily loss limit (default 3 %) — bot halts automatically
- Duplicate-trade prevention via live position check
- CSV trade journal (`trades.csv`)
- Telegram notifications (trade alerts, errors, daily limit)
- Weekend market-hours detection
- Automatic session refresh on 401 / idle timeout
- Exponential back-off on errors
- Modular structure: `broker`, `strategy`, `risk`, `utils`

## Project structure

```
Mt5bot/
├── main.py          # Entry point / main loop
├── config.py        # All settings loaded from .env
├── bot/
│   ├── broker.py    # Capital.com REST client
│   ├── strategy.py  # Indicator calculations & signal logic
│   ├── risk.py      # Position sizing, daily limits, duplicate guard
│   └── utils.py     # Logging, CSV journal, Telegram
├── requirements.txt
├── .env.example
└── .gitignore
```

## Quick start

```bash
# 1. Clone and enter the repo
git clone https://github.com/your-user/Mt5bot.git
cd Mt5bot

# 2. Create a virtual environment
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure credentials
cp .env.example .env
# Edit .env with your Capital.com API key, email, password

# 5. Run (start with demo env!)
python main.py
```

## Configuration (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `CAPITAL_API_KEY` | — | Capital.com API key |
| `CAPITAL_EMAIL` | — | Account email |
| `CAPITAL_PASSWORD` | — | Account password |
| `CAPITAL_ENV` | `demo` | `demo` or `live` |
| `SYMBOL` | `EURUSD` | Trading instrument epic |
| `TIMEFRAME` | `HOUR` | Candle resolution |
| `RISK_PER_TRADE` | `0.01` | Fraction of balance risked per trade |
| `STOP_LOSS_PIPS` | `20` | Stop distance in pips |
| `TAKE_PROFIT_PIPS` | `40` | TP distance in pips |
| `MAX_TRADES_PER_DAY` | `3` | Hard cap on daily entries |
| `DAILY_LOSS_LIMIT` | `0.03` | Halt threshold (3 % drawdown) |
| `TELEGRAM_BOT_TOKEN` | *(blank)* | Optional Telegram bot token |
| `TELEGRAM_CHAT_ID` | *(blank)* | Optional Telegram chat ID |

## Telegram setup (optional)

1. Create a bot via [@BotFather](https://t.me/BotFather) and copy the token.
2. Start a chat with your bot; get your chat ID from `https://api.telegram.org/bot<TOKEN>/getUpdates`.
3. Add both values to `.env`.

## Risk disclaimer

This software is for educational purposes. Trading forex involves substantial risk of loss. Always test on a **demo account** before using live funds. Past strategy performance does not guarantee future results.
