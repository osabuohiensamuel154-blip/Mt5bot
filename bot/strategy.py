"""EMA50 / EMA200 + RSI pullback strategy on H1 candles.

Entry requires ALL seven conditions to be true simultaneously:
  1. EMA50 on correct side of EMA200       (trend direction)
  2. Price on correct side of EMA200        (price confirms trend)
  3. RSI in pullback zone                   (timing — not chasing)
  4. RSI turning in trade direction         (momentum recovering)
  5. Closing candle body in trade direction (price action confirmation)
  6. EMA50 slope in trade direction         (trend still active)
  7. Meaningful EMA50/EMA200 separation     (not near a crossover)
"""
import logging
import pandas as pd

logger = logging.getLogger(__name__)

MIN_CANDLES = 220

# EMA50 must be at least this far from EMA200 (as a fraction of price)
# 0.0003 = ~3 pips on EURUSD — prevents trading right at the crossover
_MIN_EMA_GAP = 0.0003

# RSI ranges — tighter than a basic strategy to reduce marginal setups
_BUY_RSI_LOW  = 45
_BUY_RSI_HIGH = 58   # was 60 — keeps us out of late/overextended bounces
_SELL_RSI_LOW  = 42
_SELL_RSI_HIGH = 55


def build_dataframe(candles: list) -> pd.DataFrame | None:
    """Convert Capital.com price list to a clean OHLC DataFrame."""
    if not candles:
        logger.warning("Empty candle list received")
        return None

    df = pd.DataFrame(candles)

    def _bid(col: str) -> pd.Series:
        return df[col].apply(lambda x: x.get("bid", 0) if isinstance(x, dict) else x)

    df["open"]  = pd.to_numeric(_bid("openPrice"),  errors="coerce")
    df["high"]  = pd.to_numeric(_bid("highPrice"),  errors="coerce")
    df["low"]   = pd.to_numeric(_bid("lowPrice"),   errors="coerce")
    df["close"] = pd.to_numeric(_bid("closePrice"), errors="coerce")

    df = df.dropna(subset=["close"]).reset_index(drop=True)
    return df


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder-smoothed RSI (matches MetaTrader / TradingView)."""
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    alpha = 1.0 / period
    avg_gain = gain.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ema50"]  = _ema(df["close"], 50)
    df["ema200"] = _ema(df["close"], 200)
    df["rsi"]    = _rsi(df["close"], 14)
    return df


def _log_filters(label: str, checks: dict[str, bool]) -> None:
    results = "  ".join(f"{k}={'OK' if v else 'NO'}" for k, v in checks.items())
    logger.info("[%s] %s", label, results)


def check_signal(df: pd.DataFrame | None) -> str:
    if df is None or len(df) < MIN_CANDLES:
        logger.warning("Insufficient candles: %d (need %d)", len(df) if df is not None else 0, MIN_CANDLES)
        return "HOLD"

    df = calculate_indicators(df)

    c0 = df.iloc[-1]   # current (latest closed) candle
    c1 = df.iloc[-2]   # one candle back
    c5 = df.iloc[-6]   # five candles back — used for EMA slope

    price  = c0["close"]
    ema50  = c0["ema50"]
    ema200 = c0["ema200"]
    rsi    = c0["rsi"]
    rsi_prev = c1["rsi"]

    if pd.isna(ema200) or pd.isna(rsi) or pd.isna(rsi_prev):
        logger.warning("Indicators not yet converged")
        return "HOLD"

    ema_gap = abs(ema50 - ema200) / ema200

    logger.info(
        "Price=%.5f  EMA50=%.5f  EMA200=%.5f  RSI=%.1f (prev=%.1f)  EMAGap=%.4f%%",
        price, ema50, ema200, rsi, rsi_prev, ema_gap * 100,
    )

    # ── BUY: all 7 conditions ──────────────────────────────────────
    buy_checks = {
        "trend":     ema50 > ema200,                        # 1. golden-cross regime
        "price":     price > ema200,                        # 2. price above LT average
        "rsi_zone":  _BUY_RSI_LOW <= rsi <= _BUY_RSI_HIGH, # 3. pullback zone
        "rsi_up":    rsi > rsi_prev,                        # 4. RSI momentum recovering
        "bull_candle": c0["close"] > c0["open"],            # 5. green candle confirms
        "ema_slope": ema50 > c5["ema50"],                   # 6. EMA50 still rising
        "ema_gap":   ema_gap > _MIN_EMA_GAP,                # 7. not near crossover
    }
    if all(buy_checks.values()):
        _log_filters("BUY", buy_checks)
        return "BUY"
    if ema50 > ema200:  # only log near-misses when trend is right
        _log_filters("BUY?", buy_checks)

    # ── SELL: all 7 conditions ─────────────────────────────────────
    sell_checks = {
        "trend":       ema50 < ema200,                          # 1. death-cross regime
        "price":       price < ema200,                          # 2. price below LT average
        "rsi_zone":    _SELL_RSI_LOW <= rsi <= _SELL_RSI_HIGH,  # 3. bounce zone
        "rsi_down":    rsi < rsi_prev,                          # 4. RSI momentum falling
        "bear_candle": c0["close"] < c0["open"],                # 5. red candle confirms
        "ema_slope":   ema50 < c5["ema50"],                     # 6. EMA50 still falling
        "ema_gap":     ema_gap > _MIN_EMA_GAP,                  # 7. not near crossover
    }
    if all(sell_checks.values()):
        _log_filters("SELL", sell_checks)
        return "SELL"
    if ema50 < ema200:
        _log_filters("SELL?", sell_checks)

    return "HOLD"
