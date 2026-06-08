"""Technical indicator utilities for FX markets using optimized pandas/numpy operations."""

import numpy as np
import pandas as pd
from typing import Optional

def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Average True Range (Vectorized)."""
    h = pd.Series(high)
    l = pd.Series(low)
    c = pd.Series(close)

    tr1 = h - l
    tr2 = (h - c.shift(1)).abs()
    tr3 = (l - c.shift(1)).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_vals = tr.rolling(window=period).mean() # Simple Moving Average for ATR
    return atr_vals.values

def rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """Relative Strength Index (Vectorized)."""
    delta = pd.Series(close).diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss.replace(0, 1e-10)
    rsi_vals = 100 - (100 / (1 + rs))
    return rsi_vals.values

def adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Average Directional Index (Vectorized)."""
    h = pd.Series(high)
    l = pd.Series(low)
    c = pd.Series(close)

    up = h.diff()
    down = -l.diff()

    plus_dm = up.where((up > down) & (up > 0), 0)
    minus_dm = down.where((down > up) & (down > 0), 0)

    atr_v = pd.Series(atr(high, low, close, period))

    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr_v.replace(0, 1e-10))
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr_v.replace(0, 1e-10))

    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-10) * 100
    adx_vals = dx.rolling(window=period).mean()
    return adx_vals.values

def bollinger_bands(close: np.ndarray, period: int = 20, std_dev: float = 2.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Bollinger Bands (Vectorized)."""
    s = pd.Series(close)
    ma = s.rolling(window=period).mean()
    std = s.rolling(window=period).std()

    upper = ma + (std_dev * std)
    lower = ma - (std_dev * std)
    bandwidth = (upper - lower) / ma.replace(0, 1e-10)

    return upper.values, lower.values, bandwidth.values

def rolling_volatility(close: np.ndarray, period: int = 20) -> np.ndarray:
    """Annualised rolling volatility (Vectorized)."""
    log_returns = np.log(pd.Series(close) / pd.Series(close).shift(1))
    vol = log_returns.rolling(window=period).std() * np.sqrt(252)
    return vol.values

def zscore(series: np.ndarray, period: int = 20) -> np.ndarray:
    """Rolling z-score (Vectorized)."""
    s = pd.Series(series)
    return ((s - s.rolling(window=period).mean()) / s.rolling(window=period).std().replace(0, 1e-10)).values
