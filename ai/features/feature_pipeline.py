"""Feature engineering pipeline for FX regime detection.

Transforms raw OHLCV data into a feature vector suitable for
the HMM regime classifier. Features are designed to capture:
- Trend strength and direction
- Volatility regime
- Mean-reversion likelihood
- Microstructure noise
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional

from .indicators import (
    atr,
    rsi,
    adx,
    bollinger_bands,
    rolling_volatility,
    zscore,
)


@dataclass
class FeatureConfig:
    """Configuration for feature extraction."""

    trend_period: int = 14
    vol_period: int = 20
    bb_period: int = 20
    bb_std: float = 2.0
    rsi_period: int = 14
    max_lookback: int = 100
    # Which features to include
    use_adx: bool = True
    use_rsi: bool = True
    use_bb_width: bool = True
    use_volatility: bool = True
    use_volume: bool = True
    use_hurst: bool = True
    feature_names: list[str] = field(default_factory=list, init=False)

    def __post_init__(self):
        names = []
        if self.use_adx:
            names.extend(["adx", "plus_di", "minus_di"])
        if self.use_rsi:
            names.append("rsi")
        if self.use_bb_width:
            names.append("bb_width")
        if self.use_volatility:
            names.append("volatility")
        if self.use_volume:
            names.append("volume_ratio")
        if self.use_hurst:
            names.append("hurst_exponent")
        self.feature_names = names


def _hurst_exponent(series: np.ndarray, max_lag: int = 20) -> float:
    """Estimate Hurst exponent via R/S analysis.

    H < 0.5 → mean-reverting (ranging)
    H ≈ 0.5 → random walk
    H > 0.5 → trending
    """
    if len(series) < max_lag * 2 or np.std(series) < 1e-10:
        return 0.5
    lags = range(2, min(max_lag, len(series) // 2))
    tau = []
    for lag in lags:
        # Split series into chunks of length `lag`
        n = len(series)
        chunks = n // lag
        if chunks < 2:
            continue
        rs_vals = []
        for i in range(chunks):
            chunk = series[i * lag : (i + 1) * lag]
            mean = np.mean(chunk)
            deviations = chunk - mean
            Z = np.cumsum(deviations)
            R = np.max(Z) - np.min(Z)
            S = np.std(chunk, ddof=1)
            if S > 1e-10:
                rs_vals.append(R / S)
        if rs_vals:
            tau.append(np.mean(rs_vals))
    if len(tau) < 3:
        return 0.5
    try:
        log_lags = np.log(list(lags)[: len(tau)])
        log_tau = np.log(tau)
        coeffs = np.polyfit(log_lags, log_tau, 1)
        return float(coeffs[0])
    except (np.linalg.LinAlgError, ValueError):
                return 0.5


def extract_features(
    ohlcv: pd.DataFrame,
    config: Optional[FeatureConfig] = None,
) -> tuple[np.ndarray, list[str]]:
    """Extract feature matrix from OHLCV data.

    Args:
        ohlcv: DataFrame with columns [open, high, low, close, volume] (indexed by time)
        config: Feature configuration

    Returns:
        (feature_matrix, feature_names)
        feature_matrix: (n_samples, n_features) numpy array
    """
    if config is None:
        config = FeatureConfig()

    close = ohlcv["close"].values.astype(np.float64)
    high = ohlcv["high"].values.astype(np.float64)
    low = ohlcv["low"].values.astype(np.float64)
    volume = ohlcv.get("volume", pd.Series(np.ones(len(ohlcv)))).values.astype(np.float64)

    n = len(close)
    features = np.full((n, len(config.feature_names)), np.nan)
    col = 0

    # ADX + directional indicators
    if config.use_adx:
        adx_vals = adx(high, low, close, config.trend_period)
        # Plus DI and Minus DI approximation
        up = high[1:] - high[:-1]
        down = low[:-1] - low[1:]
        plus_dm = np.where((up > down) & (up > 0), up, 0.0)
        minus_dm = np.where((down > up) & (down > 0), down, 0.0)
        atr_vals = atr(high, low, close, config.trend_period)
        plus_di = np.full(n, np.nan)
        minus_di = np.full(n, np.nan)
        for i in range(config.trend_period, n):
            if atr_vals[i] > 1e-10:
                plus_di[i] = 100 * np.mean(plus_dm[i - config.trend_period : i]) / atr_vals[i]
                minus_di[i] = 100 * np.mean(minus_dm[i - config.trend_period : i]) / atr_vals[i]
        features[:, col] = adx_vals
        features[:, col + 1] = plus_di
        features[:, col + 2] = minus_di
        col += 3

    # RSI
    if config.use_rsi:
        features[:, col] = rsi(close, config.rsi_period)
        col += 1

    # Bollinger Band width (normalized)
    if config.use_bb_width:
        _, _, bbw = bollinger_bands(close, config.bb_period, config.bb_std)
        features[:, col] = bbw
        col += 1

    # Rolling volatility
    if config.use_volatility:
        features[:, col] = rolling_volatility(close, config.vol_period)
        col += 1

    # Volume ratio (current / rolling average)
    if config.use_volume:
        vol_ma = np.full(n, np.nan)
        for i in range(config.vol_period, n):
            vol_ma[i] = np.mean(volume[i - config.vol_period : i])
        features[:, col] = volume / np.maximum(vol_ma, 1e-10)
        col += 1

    # Hurst exponent
    if config.use_hurst:
        for i in range(config.max_lookback, n):
            features[i, col] = _hurst_exponent(
                close[i - config.max_lookback : i], max_lag=20
            )
        col += 1

    return features, config.feature_names


def extract_regime_features(
    ohlcv: pd.DataFrame,
    config: Optional[FeatureConfig] = None,
) -> np.ndarray:
    """Extract and normalise features for regime detection.

    Returns a clean matrix with NaN rows removed at the start
    (due to lookback periods) and z-score normalised.
    """
    if config is None:
        config = FeatureConfig()

    raw_features, names = extract_features(ohlcv, config)

    # Find first valid index
    first_valid = np.where(~np.isnan(raw_features).any(axis=1))[0]
    if len(first_valid) == 0:
        raise ValueError("No valid features could be extracted from the data")

    start = first_valid[0]
    features = raw_features[start:].copy()

    # Z-score normalise each feature
    for j in range(features.shape[1]):
        col_data = features[:, j]
        valid = ~np.isnan(col_data)
        if valid.sum() > 1:
            mean = np.mean(col_data[valid])
            std = np.std(col_data[valid], ddof=1)
            if std > 1e-10:
                features[:, j] = (features[:, j] - mean) / std

    # Any remaining NaN → 0
    features = np.nan_to_num(features, nan=0.0)

    return features