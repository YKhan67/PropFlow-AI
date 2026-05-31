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
    min_time_between_trades_minutes: int = 5


class SignalGate:
    """Rule-based gate that filters trading signals.

    Acts as the 'rule-based' component of the hybrid engine.
    Each filter returns a decision; the most restrictive wins.
    """

    def __init__(
        self,
        vol_config: Optional[VolatilityFilterConfig] = None,
        dd_config: Optional[DrawdownFilterConfig] = None,
    ):
        self.vol_config = vol_config or VolatilityFilterConfig()
        self.dd_config = dd_config or DrawdownFilterConfig()
        self._signal_counter: int = 0
        self._last_block_bar: int = -self.vol_config.signal_cooldown_bars
        self._daily_pnl: float = 0.0
        self._total_pnl: float = 0.0
        self._starting_equity: float = 100000.0  # default, set via configure()

    def configure(self, starting_equity: float, daily_pnl: float = 0.0, total_pnl: float = 0.0):
        """Update account state."""
        self._starting_equity = starting_equity
        self._daily_pnl = daily_pnl
        self._total_pnl = total_pnl

    def evaluate(
        self,
        ohlcv_row: pd.Series,
        prev_close: float,
        bar_index: int,
        is_friday: bool = False,
        is_monday: bool = False,
        atr_value: Optional[float] = None,
        median_atr: Optional[float] = None,
    ) -> tuple[FilterDecision, str]:
        """Evaluate all rule-based filters on a single bar.

        Args:
            ohlcv_row: Single row of OHLCV data
            prev_close: Previous bar close price
            bar_index: Current bar index
            is_friday/is_monday: Day-of-week flags
            atr_value: Precomputed ATR if available
            median_atr: Median ATR for the lookback period

        Returns:
            (FilterDecision, reason_string)
        """
        close = float(ohlcv_row["close"])
        high = float(ohlcv_row["high"])
        low = float(ohlcv_row["low"])
        open_price = float(ohlcv_row["open"])

        # 1. Gap detection
        gap_pct = abs(open_price - prev_close) / max(prev_close, 1e-10)
        if gap_pct > self.vol_config.max_gap_percent:
            return FilterDecision.DELAY, (
                f"Gap detected: {gap_pct:.4%} > {self.vol_config.max_gap_percent:.4%}"
            )

        # 2. ATR spike detection
        if atr_value is not None and median_atr is not None and median_atr > 1e-10:
            atr_ratio = atr_value / median_atr
            if atr_ratio > self.vol_config.atr_threshold_multiple:
                return FilterDecision.BLOCK, (
                    f"ATR spike: {atr_ratio:.2f}x median > {self.vol_config.atr_threshold_multiple}x"
                )

        # 3. Time-based filters
        if is_friday and bar_index >= -self.vol_config.avoid_friday_close_bars:
            return FilterDecision.DELAY, "Friday close cooldown"
        if is_monday and bar_index <= self.vol_config.avoid_monday_open_bars:
            return FilterDecision.DELAY, "Monday open cooldown"

        # 4. Consecutive signal cooldown
        bars_since_block = bar_index - self._last_block_bar
        if bars_since_block < self.vol_config.signal_cooldown_bars:
            return FilterDecision.DELAY, (
                f"Signal cooldown: {bars_since_block}/{self.vol_config.signal_cooldown_bars} bars"
            )

        # 5. Drawdown checks
        daily_dd_pct = -self._daily_pnl / self._starting_equity * 100
        total_dd_pct = -self._total_pnl / self._starting_equity * 100

        if total_dd_pct >= self.dd_config.total_drawdown_limit_pct:
            return FilterDecision.BLOCK, (
                f"Total drawdown limit: {total_dd_pct:.1f}% >= {self.dd_config.total_drawdown_limit_pct}%"
            )
        if daily_dd_pct >= self.dd_config.daily_drawdown_limit_pct:
            return FilterDecision.BLOCK, (
                f"Daily drawdown limit: {daily_dd_pct:.1f}% >= {self.dd_config.daily_drawdown_limit_pct}%"
            )
        if daily_dd_pct >= self.dd_config.daily_loss_soft_limit_pct:
            return FilterDecision.REDUCE, (
                f"Daily loss soft limit: {daily_dd_pct:.1f}% > {self.dd_config.daily_loss_soft_limit_pct}%"
            )

        # 6. Spread check (approximate using high-low range)
        spread_pips = (high - low) * 10000  # rough pips for FX
        if spread_pips > self.dd_config.max_spread_pips * 3:  # 3x typical spread = red flag
            return FilterDecision.DELAY, f"Wide spread: {spread_pips:.1f} pips"

        return FilterDecision.PASS, "All filters passed"

    def count_signal(self) -> None:
        """Increment signal counter (used for consecutive signal limit)."""
        self._signal_counter += 1

    def register_block(self, bar_index: int) -> None:
        """Record a blocked signal for cooldown tracking."""
        self._last_block_bar = bar_index