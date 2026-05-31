"""Technical indicator utilities for FX markets."""

import numpy as np
from typing import Optional

try:
    from numba import jit
    _HAVE_NUMBA = True
except ImportError:
    _HAVE_NUMBA = False
    jit = lambda **kwargs: lambda f: f  # no-op decorator


if _HAVE_NUMBA:

    @jit(nopython=True)
    def _rolling_rms(data: np.ndarray, window: int) -> np.ndarray:
        result = np.full_like(data, np.nan)
        for i in range(window - 1, len(data)):
            sq = 0.0
            for j in range(window):
                sq += data[i - j] ** 2
            result[i] = np.sqrt(sq / window)
        return result
else:

    def _rolling_rms(data: np.ndarray, window: int) -> np.ndarray:
        result = np.full_like(data, np.nan)
        for i in range(window - 1, len(data)):
            sq = 0.0
            for j in range(window):
                sq += data[i - j] ** 2
            result[i] = np.sqrt(sq / window)
        return result


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Average True Range."""
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1]),
        ),
    )
    tr_full = np.empty_like(close)
    tr_full[0] = high[0] - low[0]
    tr_full[1:] = tr
    out = np.full_like(close, np.nan)
    out[period - 1] = np.mean(tr_full[:period])
    for i in range(period, len(close)):
        out[i] = (out[i - 1] * (period - 1) + tr_full[i]) / period
    return out


def rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """Relative Strength Index."""
    delta = np.diff(close)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = np.full_like(close, np.nan)
    avg_loss = np.full_like(close, np.nan)
    avg_gain[period] = np.mean(gain[:period])
    avg_loss[period] = np.mean(loss[:period])
    for i in range(period + 1, len(close)):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gain[i - 1]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + loss[i - 1]) / period
    rs = avg_gain / np.maximum(avg_loss, 1e-10)
    rsi_vals = 100 - (100 / (1 + rs))
    return rsi_vals


def adx(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """Average Directional Index - trend strength indicator."""
    up = high[1:] - high[:-1]
    down = low[:-1] - low[1:]
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])),
    )
    # Smooth
    atr_vals = atr(high, low, close, period)
    plus_di = np.full_like(close, np.nan)
    minus_di = np.full_like(close, np.nan)
    for i in range(period, len(close)):
        if atr_vals[i] > 1e-10:
            plus_di[i] = 100 * np.mean(plus_dm[i - period : i]) / atr_vals[i]
            minus_di[i] = 100 * np.mean(minus_dm[i - period : i]) / atr_vals[i]
    dx = np.abs(plus_di - minus_di) / np.maximum((plus_di + minus_di), 1e-10) * 100
    adx_vals = np.full_like(close, np.nan)
    for i in range(period * 2 - 1, len(close)):
        adx_vals[i] = np.mean(dx[i - period + 1 : i + 1])
    return adx_vals


def bollinger_bands(
    close: np.ndarray, period: int = 20, std_dev: float = 2.0
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Bollinger Bands."""
    rolling_mean = np.full_like(close, np.nan)
    rolling_std = np.full_like(close, np.nan)
    for i in range(period - 1, len(close)):
        segment = close[i - period + 1 : i + 1]
        rolling_mean[i] = np.mean(segment)
        rolling_std[i] = np.std(segment, ddof=1)
    upper = rolling_mean + std_dev * rolling_std
    lower = rolling_mean - std_dev * rolling_std
    bandwidth = (upper - lower) / np.maximum(rolling_mean, 1e-10)
    return upper, lower, bandwidth


def rolling_volatility(close: np.ndarray, period: int = 20) -> np.ndarray:
    """Annualised rolling volatility from log returns."""
    log_returns = np.diff(np.log(np.maximum(close, 1e-10)))
    vol = np.full_like(close, np.nan)
    for i in range(period, len(log_returns)):
        vol[i + 1] = np.std(log_returns[i - period : i], ddof=1) * np.sqrt(252)
    return vol


def zscore(series: np.ndarray, period: int = 20) -> np.ndarray:
    """Rolling z-score."""
    rolling_mean = np.full_like(series, np.nan)
    rolling_std = np.full_like(series, np.nan)
    for i in range(period - 1, len(series)):
        seg = series[i - period + 1 : i + 1]
        rolling_mean[i] = np.mean(seg)
        rolling_std[i] = np.std(seg, ddof=1)
    return (series - rolling_mean) / np.maximum(rolling_std, 1e-10)