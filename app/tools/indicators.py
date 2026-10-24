"""Technical indicators computed in plain Python.

The LLM never calculates numbers; these functions do it and the Technical
Analyst agent only interprets the results.
"""

from math import exp

import numpy as np
from statistics import mean, pstdev


def sma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return mean(values[-window:])


def ema_series(values: list[float], window: int) -> list[float] | None:
    """Exponential moving average over the whole series (seeded with the SMA)."""
    if len(values) < window:
        return None
    seed = mean(values[:window])
    alpha = 2.0 / (window + 1)
    out = [seed]
    for value in values[window:]:
        out.append(alpha * value + (1 - alpha) * out[-1])
    return out


def rsi(closes: list[float], period: int = 14) -> float | None:
    """Simple-average RSI (not Wilder smoothing - good enough for an MVP)."""
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for prev, cur in zip(closes[-(period + 1) :], closes[-period:]):
        change = cur - prev
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = mean(gains)
    avg_loss = mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict | None:
    """MACD line, signal line and histogram (last values only)."""
    fast_ema = ema_series(closes, fast)
    slow_ema = ema_series(closes, slow)
    if fast_ema is None or slow_ema is None:
        return None
    # Re-align: both series end at the last close; zip from the end.
    offset = len(fast_ema) - len(slow_ema)
    macd_line = [f - s for f, s in zip(fast_ema[offset:], slow_ema)]
    signal_ema = ema_series(macd_line, signal)
    if signal_ema is None:
        return None
    return {
        "macd": round(macd_line[-1], 3),
        "macd_signal": round(signal_ema[-1], 3),
        "macd_histogram": round(macd_line[-1] - signal_ema[-1], 3),
    }


def bollinger(closes: list[float], window: int = 20, num_std: float = 2.0) -> dict | None:
    """Bollinger band position: percent_b 0.0 = at the lower band, 1.0 = at the upper."""
    if len(closes) < window:
        return None
    mid = mean(closes[-window:])
    dev = pstdev(closes[-window:])
    upper, lower = mid + num_std * dev, mid - num_std * dev
    price = closes[-1]
    percent_b = (price - lower) / (upper - lower) if upper > lower else None
    return {
        "bollinger_percent_b": round(percent_b, 3) if percent_b is not None else None,
        "bollinger_width_pct": round((upper - lower) / mid * 100, 2) if mid else None,
    }


def atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float | None:
    """Average true range (simple average of the last `period` true ranges)."""
    if not highs or len(highs) != len(lows) or len(highs) != len(closes):
        return None
    if len(closes) < period + 1:
        return None
    ranges = []
    for prev_close, high, low in zip(closes[-(period + 1) :], highs[-period:], lows[-period:]):
        ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    return mean(ranges)


def pct_change(closes: list[float], lookback_days: int) -> float | None:
    """Percent change over the last N trading days."""
    if len(closes) < lookback_days + 1 or closes[-lookback_days - 1] == 0:
        return None
    return (closes[-1] / closes[-lookback_days - 1] - 1.0) * 100.0


def annualized_volatility(closes: list[float], window: int = 20) -> float | None:
    """Annualized stdev of daily returns over the last `window` days."""
    if len(closes) < window + 1:
        return None
    returns = [
        cur / prev - 1.0 for prev, cur in zip(closes[-(window + 1) :], closes[-window:])
    ]
    return pstdev(returns) * (252**0.5) * 100.0


def volume_stats(volumes: list[float], window: int = 20) -> dict:
    """Average volume and how loud today is relative to it."""
    if not volumes or volumes[-1] in (None, 0):
        return {}
    recent = [v for v in volumes[-window:] if v is not None]
    if not recent:
        return {}
    avg = mean(recent)
    if avg == 0:
        return {}
    return {
        "avg_volume_20d": round(avg),
        "relative_volume": round(volumes[-1] / avg, 2),
    }


RIDGE_LAGS = 5
RIDGE_ALPHA = 1.0


def _ridge_fit(x: np.ndarray, y: np.ndarray):
    """Ridge on z-scored lagged-return features; returns a predict(rows) closure.

    Features are daily log returns (tiny, near-identical scale), so the design
    matrix is z-scored per column: otherwise RIDGE_ALPHA drowns the data term
    and every coefficient shrinks to zero.
    """
    x_mean, x_std = x.mean(axis=0), x.std(axis=0)
    x_std = np.where(x_std > 0, x_std, 1.0)
    y_mean = float(y.mean())
    xs = (x - x_mean) / x_std
    beta = np.linalg.solve(
        xs.T @ xs + RIDGE_ALPHA * np.eye(xs.shape[1]), xs.T @ (y - y_mean)
    )

    def predict(rows: np.ndarray) -> np.ndarray:
        return ((rows - x_mean) / x_std) @ beta + y_mean

    return predict


def historical_forecast(
    closes: list[float], horizon: int = 5, window: int = 120
) -> dict | None:
    """Project prices with a ridge regression on lagged daily log returns.

    One fit per step out to `horizon` (direct multi-step), so a far step never
    compounds the errors of near ones. A baseline, not a probability: the
    reported R2 is out-of-sample skill at the full horizon, and daily-return
    predictability is near zero by nature, so a non-positive R2 means "no
    local signal" rather than a broken model.
    """
    if horizon < 1 or len(closes) < 30:
        return None
    sample = closes[-window:]
    if any(price <= 0 for price in sample):
        return None

    logs = np.log(np.asarray(sample, dtype=float))
    rets = np.diff(logs)
    m = len(sample)
    # Rows for the farthest step: one feature window per start day.
    if m - RIDGE_LAGS - horizon < 20:
        return None
    windows = np.lib.stride_tricks.sliding_window_view(rets, RIDGE_LAGS)

    def targets(step: int, rows: int) -> np.ndarray:
        """Step-day log return starting where each feature window ends.

        Feature window j ends at day t = RIDGE_LAGS + j, so its target is
        y_all[t] = logs[t+step] - logs[t].
        """
        return (logs[step:] - logs[:-step])[RIDGE_LAGS : RIDGE_LAGS + rows]

    x_last = windows[-1]
    path = []
    for step in range(1, horizon + 1):
        rows = m - step - RIDGE_LAGS
        predict = _ridge_fit(windows[:rows], targets(step, rows))
        path.append(round(sample[-1] * exp(float(predict(x_last))), 2))

    # Skill stat at the full horizon: hold out the last 30 fits when there is
    # room, otherwise score the in-sample fit (small histories only).
    rows = m - horizon - RIDGE_LAGS
    y = targets(horizon, rows)
    if rows >= 50:
        split = rows - 30
        predicted = _ridge_fit(windows[:split], y[:split])(windows[split:rows])
        actual = y[split:]
    else:
        predicted = _ridge_fit(windows[:rows], y)(windows[:rows])
        actual = y
    resid = float(np.sum((actual - predicted) ** 2))
    total = float(np.sum((actual - actual.mean()) ** 2))
    r_squared = 1.0 if (total == 0 and resid == 0) else (0.0 if total == 0 else 1 - resid / total)
    r_squared = max(-1.0, min(1.0, r_squared))

    return {
        "forecast_price_5d": path[-1],
        "forecast_change_5d_pct": round((path[-1] / closes[-1] - 1) * 100, 2),
        "forecast_trend_r2": round(r_squared, 3),
        "forecast_window_days": len(sample),
        "forecast_horizon_days": horizon,
        "forecast_path": path,
        "forecast_method": "ridge_lag",
    }


def compute_indicators(
    closes: list[float],
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    volumes: list[float] | None = None,
) -> dict:
    """All indicators the Technical Analyst gets to interpret."""
    if len(closes) < 2:
        return {"error": "not enough price history"}

    price = closes[-1]
    sma20 = sma(closes, 20)
    sma50 = sma(closes, 50)
    momentum = pct_change(closes, 10)

    out = {
        "price": round(price, 2),
        "sma_20": round(sma20, 2) if sma20 else None,
        "sma_50": round(sma50, 2) if sma50 else None,
        "rsi_14": round(rsi(closes), 1) if rsi(closes) is not None else None,
        "momentum_10d_pct": round(momentum, 2) if momentum is not None else None,
        "volatility_annualized_pct": (
            round(annualized_volatility(closes), 2)
            if annualized_volatility(closes) is not None
            else None
        ),
        "change_1d_pct": _safe_round(pct_change(closes, 1)),
        "change_5d_pct": _safe_round(pct_change(closes, 5)),
        "change_21d_pct": _safe_round(pct_change(closes, 21)),
        "change_63d_pct": _safe_round(pct_change(closes, 63)),
        "price_above_sma20": (price > sma20) if sma20 else None,
        "sma20_above_sma50": (sma20 > sma50) if (sma20 and sma50) else None,
        "history_days": len(closes),
    }

    macd_data = macd(closes)
    if macd_data:
        out.update(macd_data)
    boll_data = bollinger(closes)
    if boll_data:
        out.update(boll_data)

    if highs and lows:
        atr_value = atr(highs, lows, closes)
        if atr_value is not None:
            out["atr_14"] = round(atr_value, 2)
            out["atr_pct_of_price"] = round(atr_value / price * 100, 2) if price else None
    if volumes:
        out.update(volume_stats(volumes))
    forecast = historical_forecast(closes)
    if forecast:
        out.update(forecast)
    return out


def _safe_round(value: float | None, digits: int = 2) -> float | None:
    return round(value, digits) if value is not None else None
