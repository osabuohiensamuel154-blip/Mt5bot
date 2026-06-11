"""Logging setup, CSV trade journal, Telegram notifications, market hours."""
import csv
import logging
import os
import requests
from datetime import datetime, timezone

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

_TRADE_LOG = "trades.csv"
_LOG_FIELDS = [
    "timestamp_utc", "epic", "direction", "size",
    "entry_price", "stop_pips", "tp_pips", "deal_ref", "status", "notes",
]


# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------

def setup_logging(level: int = logging.INFO) -> None:
    fmt = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
    logging.basicConfig(
        level=level,
        format=fmt,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("bot.log", encoding="utf-8"),
        ],
    )


# ------------------------------------------------------------------
# Trade journal
# ------------------------------------------------------------------

def log_trade(
    epic: str,
    direction: str,
    size: int,
    entry_price: float,
    stop_pips: int,
    tp_pips: int,
    deal_ref: str = "",
    status: str = "OPENED",
    notes: str = "",
) -> None:
    file_exists = os.path.isfile(_TRADE_LOG)
    with open(_TRADE_LOG, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_LOG_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(
            {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "epic": epic,
                "direction": direction,
                "size": size,
                "entry_price": entry_price,
                "stop_pips": stop_pips,
                "tp_pips": tp_pips,
                "deal_ref": deal_ref,
                "status": status,
                "notes": notes,
            }
        )
    logging.getLogger(__name__).info("Trade logged: %s %s %s @ %.5f", direction, size, epic, entry_price)


# ------------------------------------------------------------------
# Telegram
# ------------------------------------------------------------------

def _send_telegram(text: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
    except requests.RequestException as exc:
        logging.getLogger(__name__).warning("Telegram send failed: %s", exc)


def notify_startup(symbol: str, env: str) -> None:
    _send_telegram(
        f"<b>Forex Bot Started</b>\n"
        f"Symbol: {symbol}  |  Env: {env}\n"
        f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )


def notify_trade(direction: str, epic: str, size: int, entry: float, sl: int, tp: int) -> None:
    label = "BUY" if direction == "BUY" else "SELL"
    _send_telegram(
        f"<b>{label} Signal Executed</b>\n"
        f"Pair:  {epic}\n"
        f"Size:  {size} units\n"
        f"Entry: {entry:.5f}\n"
        f"SL:    -{sl} pips\n"
        f"TP:    +{tp} pips"
    )


def notify_daily_limit_hit(loss_pct: float) -> None:
    _send_telegram(
        f"<b>Daily Loss Limit Reached</b>\n"
        f"Loss: {loss_pct:.1%} — trading halted for today."
    )


def notify_error(msg: str) -> None:
    _send_telegram(f"<b>Bot Error</b>\n{msg[:400]}")


def notify_stopped(reason: str) -> None:
    _send_telegram(f"<b>Bot Stopped</b>\nReason: {reason}")


# ------------------------------------------------------------------
# Market hours helper
# ------------------------------------------------------------------

def is_forex_market_open() -> bool:
    """Forex is closed Saturday all day and Sunday before ~21:00 UTC."""
    now = datetime.now(timezone.utc)
    wd = now.weekday()  # 0=Mon … 5=Sat, 6=Sun
    if wd == 5:
        return False
    if wd == 6 and now.hour < 21:
        return False
    return True
