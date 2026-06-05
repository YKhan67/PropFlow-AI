"""Rule-based filters to suppress false signals during high volatility.

These are deterministic, explainable rules that act as a gate
on top of any AI-generated signals. They encode prop-firm risk
management best practices and are configurable per account.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

from ..features.indicators import atr, bollinger_bands, rolling_volatility


class FilterDecision(Enum):
    PASS = "pass"            # Signal allowed
    BLOCK = "block"          # Signal blocked entirely
    REDUCE = "reduce"        # Signal allowed with reduced size
    DELAY = "delay"          # Signal postponed pending confirmation


@dataclass
class VolatilityFilterConfig:
    """Configuration for volatility-based filtering."""

    # ATR threshold relative to median ATR (multiple)
    atr_threshold_multiple: float = 2.5
    atr_period: int = 14

    # Bollinger Band width threshold (normalized)
    max_bb_width: float = 0.15  # 15% width relative to price

    # Volatility spike detection (z-score of rolling volatility)
    vol_spike_zscore: float = 2.0
    vol_period: int = 20

    # Spread / gap detection
    max_gap_percent: float = 0.005  # 0.5% max open-to-previous-close gap

    # Consecutive signal filtering
    max_consecutive_signals: int = 3
    signal_cooldown_bars: int = 5  # bars to wait after block

    # Time-based filters (avoid trading major news events)
    avoid_friday_close_bars: int = 5  # last 5 bars before market close Friday
    avoid_monday_open_bars: int = 3  # first 3 bars Monday open


@dataclass
class DrawdownFilterConfig:
    """Configuration for drawdown-based signal suppression.

    Mirrors typical prop-firm rules:
    - Daily drawdown limit (% of starting equity)
    - Total drawdown limit (% of starting equity)
    - Max position size as % of account
    """

    daily_drawdown_limit_pct: float = 5.0
    total_drawdown_limit_pct: float = 10.0
    max_position_size_pct: float = 2.0
    daily_loss_soft_limit_pct: float = 3.0  # warning threshold
    max_spread_pips: float = 2.0
    min_time_between_trades_seconds: int = 300


import time
import datetime

class SignalGate:
    """Rule-based gate that filters trading signals."""

    def __init__(
        self,
        vol_config: Optional[VolatilityFilterConfig] = None,
        dd_config: Optional[DrawdownFilterConfig] = None,
    ):
        self.vol_config = vol_config or VolatilityFilterConfig()
        self.dd_config = dd_config or DrawdownFilterConfig()
        self._last_trade_times: dict[str, float] = {} # Symbol-specific cooldowns
        self._last_block_times: dict[str, float] = {}
        self._daily_pnl: float = 0.0
        self._total_pnl: float = 0.0
        self._starting_equity: float = 100000.0

    def configure(self, starting_equity: float, daily_pnl: float = 0.0, total_pnl: float = 0.0):
        self._starting_equity = starting_equity
        self._daily_pnl = daily_pnl
        self._total_pnl = total_pnl

    def evaluate(
        self,
        ohlcv_row: pd.Series,
        prev_close: float,
        bar_index: int,
        symbol: str = "unknown", # Added symbol param
        is_friday: bool = False,
        is_monday: bool = False,
        atr_value: Optional[float] = None,
        median_atr: Optional[float] = None,
    ) -> tuple[FilterDecision, str]:
        # ... price data ...
        close = float(ohlcv_row["close"])
        open_price = float(ohlcv_row["open"])

        # 1. Per-Symbol Cooldown
        now = time.time()
        last_trade = self._last_trade_times.get(symbol, 0)
        cooldown_seconds = self.dd_config.min_time_between_trades_seconds
        if now - last_trade < cooldown_seconds:
            return FilterDecision.DELAY, f"Cooldown active ({int(cooldown_seconds - (now - last_trade))}s left)"

        # 2. ATR spike detection
        if atr_value is not None and median_atr is not None and median_atr > 1e-10:
            atr_ratio = atr_value / median_atr
            if atr_ratio > self.vol_config.atr_threshold_multiple:
                return FilterDecision.BLOCK, f"Volatility spike ({atr_ratio:.1f}x normal)"

        # 3. Drawdown checks
        daily_dd_pct = (-self._daily_pnl / self._starting_equity * 100) if self._starting_equity > 0 else 0
        if daily_dd_pct >= self.dd_config.daily_drawdown_limit_pct:
            return FilterDecision.BLOCK, f"Daily drawdown limit reached ({daily_dd_pct:.1f}%)"

        return FilterDecision.PASS, "All filters passed"

    def count_signal(self, symbol: str = "unknown") -> None:
        self._last_trade_times[symbol] = time.time()

    def register_block(self, bar_index: int, symbol: str = "unknown") -> None:
        self._last_block_times[symbol] = time.time()
