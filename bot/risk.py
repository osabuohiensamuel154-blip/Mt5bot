"""Position sizing, daily loss limit, and duplicate-trade prevention."""
import logging
from datetime import date

from config import (
    RISK_PER_TRADE,
    DEFAULT_SL_PIPS,
    SL_PIPS,
    DAILY_LOSS_LIMIT,
    MAX_TRADES_PER_DAY,
    PIP_SIZES,
)

logger = logging.getLogger(__name__)


class RiskManager:
    def __init__(self):
        self._today: date = date.today()
        self.daily_start_balance: float | None = None
        self.trades_today: dict[str, int] = {}   # {epic: count}

    # ------------------------------------------------------------------
    # Day boundary
    # ------------------------------------------------------------------

    def _refresh_day(self, balance: float) -> None:
        today = date.today()
        if today != self._today:
            logger.info("New trading day %s — resetting counters", today)
            self._today = today
            self.daily_start_balance = balance
            self.trades_today = {}

    def set_start_balance(self, balance: float) -> None:
        if self.daily_start_balance is None:
            self.daily_start_balance = balance
            logger.info("Day-start balance: %.2f", balance)

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def calculate_position_size(self, balance: float, epic: str) -> int | None:
        """Return integer units to trade based on fixed-percentage risk."""
        risk_amount   = balance * RISK_PER_TRADE
        pip_size      = PIP_SIZES.get(epic, 0.0001)
        sl_pips       = SL_PIPS.get(epic, DEFAULT_SL_PIPS)
        risk_per_unit = sl_pips * pip_size

        if risk_per_unit <= 0:
            logger.error("Invalid pip config for %s", epic)
            return None

        size = int(risk_amount / risk_per_unit)
        size = max(size, 1)
        logger.info(
            "%s  size=%d units  (risk=%.2f  SL=%d pips  pip=%.5f)",
            epic, size, risk_amount, sl_pips, pip_size,
        )
        return size

    def _daily_loss_ok(self, current_balance: float) -> bool:
        if not self.daily_start_balance:
            return True
        loss_pct = (self.daily_start_balance - current_balance) / self.daily_start_balance
        if loss_pct >= DAILY_LOSS_LIMIT:
            logger.warning(
                "Daily loss limit reached: %.1f%% >= %.1f%%. ALL trading halted.",
                loss_pct * 100, DAILY_LOSS_LIMIT * 100,
            )
            return False
        return True

    def _max_trades_ok(self) -> bool:
        if MAX_TRADES_PER_DAY == 0:
            return True  # unlimited — strategy quality is the only gate
        total = sum(self.trades_today.values())
        if total >= MAX_TRADES_PER_DAY:
            logger.info("Max trades/day reached (%d total). Skipping.", MAX_TRADES_PER_DAY)
            return False
        return True

    @staticmethod
    def _is_duplicate(signal: str, open_positions: list, epic: str) -> bool:
        for pos in open_positions:
            direction = pos.get("position", {}).get("direction", "")
            pos_epic  = pos.get("market",   {}).get("epic", "")
            if pos_epic == epic and direction == signal:
                logger.info("Already in %s %s — skipping duplicate", signal, epic)
                return True
        return False

    # ------------------------------------------------------------------
    # Master gate
    # ------------------------------------------------------------------

    def can_trade(self, signal: str, balance: float, open_positions: list, epic: str) -> bool:
        self._refresh_day(balance)

        if signal == "HOLD":
            return False
        if not self._daily_loss_ok(balance):
            return False
        if not self._max_trades_ok():
            return False
        if self._is_duplicate(signal, open_positions, epic):
            return False
        return True

    def record_trade(self, epic: str) -> None:
        self.trades_today[epic] = self.trades_today.get(epic, 0) + 1
        total = sum(self.trades_today.values())
        cap   = str(MAX_TRADES_PER_DAY) if MAX_TRADES_PER_DAY else "∞"
        logger.info("Trades today: %d/%s across %d pairs  |  %s",
                    total, cap, len(self.trades_today), self.trades_today)
