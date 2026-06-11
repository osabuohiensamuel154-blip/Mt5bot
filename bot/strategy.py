"""EMA50 / EMA200 + RSI pullback strategy on H1 candles."""
import logging
import pandas as pd

logger = logging.getLogger(__name__)

# Minimum candles needed for EMA200 to converge reliably
MIN_CANDLES = 220


def build_dataframe(candles: list) -> pd.DataFrame | None:
    """Convert Capital.com price list to a clean OHLC DataFrame."""
    if not candles:
        logger.warning("Empty candle list received")
        return None

    df = pd.DataFrame(candles)

    def _bid(col: str) -> pd.Series:
        return df[col].apply(lambda x: x.get("bid", 0) if isinstance(x, dict) else x)

    df["open"] = pd.to_numeric(_bid("openPrice"), errors="coerce")
    df["high"] = pd.to_numeric(_bid("highPrice"), errors="coerce")
    df["low"] = pd.to_numeric(_bid("lowPrice"), errors="coerce")
    df["close"] = pd.to_numeric(_bid("closePrice"), errors="coerce")

    df = df.dropna(subset=["close"]).reset_index(drop=True)
    return df


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder-smoothed RSI (matches MetaTrader / TradingView)."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    alpha = 1.0 / period
    avg_gain = gain.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ema50"] = _ema(df["close"], 50)
    df["ema200"] = _ema(df["close"], 200)
    df["rsi"] = _rsi(df["close"], 14)
    return df


def check_signal(df: pd.DataFrame | None) -> str:
    if df is None or len(df) < MIN_CANDLES:
        count = len(df) if df is not None else 0
        logger.warning("Insufficient candles: %d (need %d)", count, MIN_CANDLES)
        return "HOLD"

    df = calculate_indicators(df)
    latest = df.iloc[-1]

    price = latest["close"]
    ema50 = latest["ema50"]
    ema200 = latest["ema200"]
    rsi = latest["rsi"]

    if pd.isna(ema200) or pd.isna(rsi):
        logger.warning("Indicators not yet converged (NaN)")
        return "HOLD"

    logger.info(
        "Price=%.5f  EMA50=%.5f  EMA200=%.5f  RSI=%.1f",
        price, ema50, ema200, rsi,
    )

    # Uptrend pullback entry
    if price > ema200 and ema50 > ema200 and 45 <= rsi <= 60:
        return "BUY"

    # Downtrend pullback entry
    if price < ema200 and ema50 < ema200 and 40 <= rsi <= 55:
        return "SELL"

    return "HOLD"
