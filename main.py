"""
Forex Strategy Bot — Capital.com
Strategy : EMA50 / EMA200 + RSI pullback (H1)
Pairs    : All configured symbols traded simultaneously each hour
Risk     : 1% per trade, 3% daily loss limit (account-wide)

Usage:
  python main.py            # continuous loop (VPS / local)
  python main.py --once     # single pass then exit (GitHub Actions cron)
  python main.py --dry-run  # full pass, real signals, NO orders placed
  python main.py --check    # connection + data test only, then exit
"""
import logging
import sys
import time
from datetime import datetime, timezone

from config import (
    CAPITAL_ENV, SYMBOLS, TIMEFRAME,
    SL_PIPS, TP_PIPS, DEFAULT_SL_PIPS, DEFAULT_TP_PIPS,
    CANDLE_COUNT, LOOP_INTERVAL,
)
from bot.broker import CapitalComClient
from bot.strategy import build_dataframe, check_signal, calculate_indicators
from bot.risk import RiskManager
from bot.utils import (
    setup_logging,
    log_trade,
    notify_startup,
    notify_trade,
    notify_daily_limit_hit,
    notify_error,
    notify_stopped,
    is_forex_market_open,
)

setup_logging()
logger = logging.getLogger(__name__)

_MAX_CONSECUTIVE_ERRORS = 10
_SYMBOL_DELAY = 1.0   # seconds between symbol API calls (rate-limit buffer)


# ── Core evaluation loop ─────────────────────────────────────────────────────

def _single_pass(client: "CapitalComClient", risk: "RiskManager", dry_run: bool = False) -> bool:
    """Evaluate every symbol once. Returns True on success, False on hard failure."""
    tag = "[DRY RUN] " if dry_run else ""
    logger.info("%s=== %s  |  %d pairs ===",
                tag, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), len(SYMBOLS))

    if not is_forex_market_open():
        logger.info("Market closed (weekend). Nothing to do.")
        return True

    balance = client.get_balance()
    if balance is None:
        logger.warning("Balance unavailable")
        return False
    logger.info("Balance: %.2f", balance)

    risk.set_start_balance(balance)

    if not risk._daily_loss_ok(balance):
        loss_pct = (risk.daily_start_balance - balance) / risk.daily_start_balance
        notify_daily_limit_hit(loss_pct)
        logger.info("Daily loss limit active — skipping all pairs.")
        return True

    # Fetch open positions once; shared across all symbol checks this pass
    open_positions = client.get_open_positions()
    trades_placed: list[str] = []

    for symbol in SYMBOLS:
        logger.info("── %s ──", symbol)
        try:
            candles = client.get_candles(symbol, TIMEFRAME, CANDLE_COUNT)
            df      = build_dataframe(candles)
            signal  = check_signal(df)
            logger.info("%s  →  %s", symbol, signal)

            if risk.can_trade(signal, balance, open_positions, epic=symbol):
                sl   = SL_PIPS.get(symbol, DEFAULT_SL_PIPS)
                tp   = TP_PIPS.get(symbol, DEFAULT_TP_PIPS)
                size = risk.calculate_position_size(balance, symbol)

                if size:
                    if dry_run:
                        entry = df.iloc[-1]["close"] if df is not None else 0.0
                        logger.info(
                            "[DRY RUN] WOULD PLACE: %s %s  size=%d  entry=%.5f  SL=%d  TP=%d",
                            signal, symbol, size, entry, sl, tp,
                        )
                        log_trade(
                            epic=symbol, direction=signal, size=size,
                            entry_price=entry, stop_pips=sl, tp_pips=tp,
                            deal_ref="DRY_RUN", status="DRY_RUN",
                            notes="dry-run — no order placed",
                        )
                        notify_trade(signal, symbol, size, entry, sl, tp, dry_run=True)
                        risk.record_trade(symbol)
                        trades_placed.append(f"[DRY] {signal} {symbol}")
                    else:
                        result = client.place_order(
                            epic=symbol, direction=signal, size=size,
                            stop_distance=sl, profit_distance=tp,
                        )
                        if result:
                            entry    = df.iloc[-1]["close"] if df is not None else 0.0
                            deal_ref = result.get("dealReference", "")
                            log_trade(
                                epic=symbol, direction=signal, size=size,
                                entry_price=entry, stop_pips=sl, tp_pips=tp,
                                deal_ref=deal_ref,
                            )
                            notify_trade(signal, symbol, size, entry, sl, tp)
                            risk.record_trade(symbol)
                            trades_placed.append(f"{signal} {symbol}")

        except Exception as exc:
            logger.error("Error on %s: %s", symbol, exc, exc_info=True)

        time.sleep(_SYMBOL_DELAY)

    if trades_placed:
        logger.info("%sTrades this pass: %s", tag, " | ".join(trades_placed))
    else:
        logger.info("%sNo trades placed this pass", tag)

    return True


# ── Modes ────────────────────────────────────────────────────────────────────

def check_connection() -> None:
    """
    --check: verify API connection, auth, balance, and candle fetch.
    Touches nothing — read-only. Safe to run at any time.
    """
    print("\n" + "=" * 55)
    print("  Capital.com Connection Check")
    print("=" * 55)

    client = CapitalComClient()

    # 1. Authentication
    print("\n[1/4] Authenticating...")
    if not client.authenticate():
        print("  FAIL  Could not authenticate.")
        print("        Check CAPITAL_API_KEY, CAPITAL_EMAIL, CAPITAL_PASSWORD in .env")
        sys.exit(1)
    print("  OK    Authenticated successfully")

    # 2. Balance
    print("\n[2/4] Fetching account balance...")
    balance = client.get_balance()
    if balance is None:
        print("  FAIL  Could not fetch balance")
        sys.exit(1)
    print(f"  OK    Balance: {balance:,.2f}")

    # 3. Candle fetch for each pair
    print(f"\n[3/4] Fetching candles for all {len(SYMBOLS)} pairs...")
    failed = []
    for symbol in SYMBOLS:
        candles = client.get_candles(symbol, TIMEFRAME, 10)
        if candles:
            df   = build_dataframe(candles)
            last = df.iloc[-1]["close"] if df is not None else 0
            print(f"  OK    {symbol:<10}  latest close = {last:.5f}  ({len(candles)} candles)")
        else:
            print(f"  FAIL  {symbol:<10}  no data returned")
            failed.append(symbol)
    if failed:
        print(f"\n  WARNING: {len(failed)} pair(s) failed: {failed}")
        print("  They may not be available on your Capital.com account/region.")

    # 4. Open positions
    print("\n[4/4] Checking open positions...")
    positions = client.get_open_positions()
    print(f"  OK    {len(positions)} open position(s)")
    for p in positions:
        epic  = p.get("market",   {}).get("epic",      "?")
        dirn  = p.get("position", {}).get("direction", "?")
        size  = p.get("position", {}).get("size",       0)
        pnl   = p.get("position", {}).get("profit",     0)
        print(f"        {dirn} {size} {epic}  P&L: {pnl:+.2f}")

    print("\n" + "=" * 55)
    print("  All checks passed. Bot is ready to trade.")
    print("=" * 55 + "\n")


def run_dry_run() -> None:
    """
    --dry-run: full signal evaluation across all pairs, NO orders placed.
    Use this to verify signals, sizing, and Telegram before going live.
    """
    logger.info("=" * 60)
    logger.info("[DRY RUN]  %d pairs  |  env=%s  |  NO ORDERS WILL BE PLACED",
                len(SYMBOLS), CAPITAL_ENV)
    logger.info("Pairs: %s", ", ".join(SYMBOLS))
    logger.info("=" * 60)

    client = CapitalComClient()
    risk   = RiskManager()

    if not client.authenticate():
        logger.critical("Authentication failed. Exiting.")
        sys.exit(1)

    balance = client.get_balance()
    if balance is not None:
        risk.set_start_balance(balance)
        logger.info("Balance: %.2f", balance)

    try:
        _single_pass(client, risk, dry_run=True)
    except Exception as exc:
        logger.error("Dry-run error: %s", exc, exc_info=True)
        sys.exit(1)

    logger.info("[DRY RUN] Complete. Check bot.log and trades.csv for results.")


def run_once() -> None:
    """Single-pass mode for GitHub Actions cron — runs once then exits."""
    logger.info("=" * 60)
    logger.info("Forex Bot (single-pass)  |  %d pairs  |  env=%s",
                len(SYMBOLS), CAPITAL_ENV)
    logger.info("Pairs: %s", ", ".join(SYMBOLS))
    logger.info("=" * 60)

    client = CapitalComClient()
    risk   = RiskManager()

    if not client.authenticate():
        logger.critical("Authentication failed. Exiting.")
        sys.exit(1)

    try:
        _single_pass(client, risk)
    except Exception as exc:
        logger.error("Single-pass error: %s", exc, exc_info=True)
        notify_error(str(exc))
        sys.exit(1)


def run_bot() -> None:
    """Continuous loop mode for VPS / always-on servers."""
    logger.info("=" * 60)
    logger.info("Forex Bot (continuous)  |  %d pairs  |  %s  |  env=%s",
                len(SYMBOLS), TIMEFRAME, CAPITAL_ENV)
    logger.info("Pairs: %s", ", ".join(SYMBOLS))
    logger.info("=" * 60)

    client = CapitalComClient()
    risk   = RiskManager()

    if not client.authenticate():
        logger.critical("Cannot authenticate. Exiting.")
        return

    balance = client.get_balance()
    if balance is not None:
        risk.set_start_balance(balance)
        logger.info("Opening balance: %.2f", balance)

    notify_startup(f"{len(SYMBOLS)} pairs", CAPITAL_ENV)

    consecutive_errors = 0
    keep_alive_counter = 0

    while True:
        try:
            loop_ts = datetime.now(timezone.utc)

            keep_alive_counter += 1
            if keep_alive_counter >= 9:
                client.keep_alive()
                keep_alive_counter = 0

            _single_pass(client, risk)
            consecutive_errors = 0

            elapsed   = (datetime.now(timezone.utc) - loop_ts).seconds
            sleep_for = max(LOOP_INTERVAL - elapsed, 60)
            logger.info("Next check in %ds", sleep_for)
            time.sleep(sleep_for)

        except KeyboardInterrupt:
            logger.info("Stopped by user")
            notify_stopped("Manual stop (Ctrl+C)")
            break

        except Exception as exc:
            consecutive_errors += 1
            logger.error(
                "Loop error [%d/%d]: %s",
                consecutive_errors, _MAX_CONSECUTIVE_ERRORS, exc,
                exc_info=True,
            )
            if consecutive_errors <= 3:
                notify_error(str(exc))
            if consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                msg = f"Halted after {_MAX_CONSECUTIVE_ERRORS} consecutive errors"
                logger.critical(msg)
                notify_stopped(msg)
                break

            backoff = min(60 * consecutive_errors, 600)
            logger.info("Back-off: sleeping %ds", backoff)
            time.sleep(backoff)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--check"   in args:
        check_connection()
    elif "--dry-run" in args:
        run_dry_run()
    elif "--once"    in args:
        run_once()
    else:
        run_bot()
