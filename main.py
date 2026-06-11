"""
Forex Strategy Bot — Capital.com
Strategy : EMA50 / EMA200 + RSI pullback (H1)
Risk     : 1% per trade, 3% daily loss limit
"""
import logging
import time
from datetime import datetime, timezone

from config import (
    CAPITAL_ENV, SYMBOL, TIMEFRAME,
    STOP_LOSS_PIPS, TAKE_PROFIT_PIPS,
    CANDLE_COUNT, LOOP_INTERVAL,
)
from bot.broker import CapitalComClient
from bot.strategy import build_dataframe, check_signal
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


def run_bot() -> None:
    logger.info("=" * 60)
    logger.info("Forex Strategy Bot  |  %s  |  %s  |  env=%s", SYMBOL, TIMEFRAME, CAPITAL_ENV)
    logger.info("=" * 60)

    client = CapitalComClient()
    risk = RiskManager()

    if not client.authenticate():
        logger.critical("Cannot authenticate. Exiting.")
        return

    balance = client.get_balance()
    if balance is not None:
        risk.set_start_balance(balance)
        logger.info("Opening balance: %.2f", balance)

    notify_startup(SYMBOL, CAPITAL_ENV)

    consecutive_errors = 0
    keep_alive_counter = 0

    while True:
        try:
            loop_ts = datetime.now(timezone.utc)
            logger.info("--- %s ---", loop_ts.strftime("%Y-%m-%d %H:%M UTC"))

            # Keep session alive every ~9 loops (~9 h) to avoid idle timeout
            keep_alive_counter += 1
            if keep_alive_counter >= 9:
                client.keep_alive()
                keep_alive_counter = 0

            # Skip outside forex market hours
            if not is_forex_market_open():
                logger.info("Market closed (weekend). Sleeping 1 hour.")
                time.sleep(3600)
                continue

            # Fetch balance
            balance = client.get_balance()
            if balance is None:
                logger.warning("Balance unavailable — skipping loop")
                time.sleep(60)
                continue
            logger.info("Balance: %.2f", balance)

            # Daily loss limit guard
            if not risk._daily_loss_ok(balance):
                loss_pct = (risk.daily_start_balance - balance) / risk.daily_start_balance
                notify_daily_limit_hit(loss_pct)
                logger.info("Daily loss limit active. Sleeping 1 hour.")
                time.sleep(3600)
                continue

            # Fetch candles and evaluate strategy
            candles = client.get_candles(SYMBOL, TIMEFRAME, CANDLE_COUNT)
            df = build_dataframe(candles)
            signal = check_signal(df)
            logger.info("Signal: %s", signal)

            # Fetch open positions for duplicate check
            open_positions = client.get_open_positions()

            # All risk gates pass → place order
            if risk.can_trade(signal, balance, open_positions):
                size = risk.calculate_position_size(balance, SYMBOL)

                if size:
                    result = client.place_order(
                        epic=SYMBOL,
                        direction=signal,
                        size=size,
                        stop_distance=STOP_LOSS_PIPS,
                        profit_distance=TAKE_PROFIT_PIPS,
                    )

                    if result:
                        entry_price = df.iloc[-1]["close"] if df is not None else 0.0
                        deal_ref = result.get("dealReference", "")

                        log_trade(
                            epic=SYMBOL,
                            direction=signal,
                            size=size,
                            entry_price=entry_price,
                            stop_pips=STOP_LOSS_PIPS,
                            tp_pips=TAKE_PROFIT_PIPS,
                            deal_ref=deal_ref,
                        )
                        notify_trade(signal, SYMBOL, size, entry_price, STOP_LOSS_PIPS, TAKE_PROFIT_PIPS)
                        risk.record_trade()

            consecutive_errors = 0

            # Sleep until the next hourly candle close
            elapsed = (datetime.now(timezone.utc) - loop_ts).seconds
            sleep_for = max(LOOP_INTERVAL - elapsed, 60)
            logger.info("Next check in %ds", sleep_for)
            time.sleep(sleep_for)

        except KeyboardInterrupt:
            logger.info("Stopped by user (KeyboardInterrupt)")
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
            logger.info("Back-off: sleeping %ds before retry", backoff)
            time.sleep(backoff)


if __name__ == "__main__":
    run_bot()
