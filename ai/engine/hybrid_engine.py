"""Hybrid Decision Engine: AI + Rule-Based Integration.

Architecture:
  1. Feature pipeline extracts indicators from raw OHLCV
  2. HMM classifies latent market regime (Trending / Ranging / Volatile)
  3. Rule-based SignalGate filters signals based on vol/drawdown/time
  4. Regime-adaptive parameters adjust sensitivity per regime class
  5. Final decision output: (action, confidence, risk_adjustment)

Key design goals:
- Minimize false signals during high volatility via multi-layer gating
- Ensure prop-firm compliance (drawdown limits, cooldowns, max sizes)
- Provide explainable decisions with traceable filter reasons
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable

import numpy as np
import pandas as pd

from ..regime.hmm_detector import RegimeHMM, HMMConfig
from ..features.feature_pipeline import FeatureConfig, extract_regime_features, extract_features
from ..utils.rule_based_filters import (
    SignalGate,
    VolatilityFilterConfig,
    DrawdownFilterConfig,
    FilterDecision,
)
from ..features.indicators import atr, bollinger_bands, rolling_volatility


class SignalType(Enum):
    LONG = "long"
    SHORT = "short"
    EXIT = "exit"
    HOLD = "hold"
    REDUCED_LONG = "reduced_long"
    REDUCED_SHORT = "reduced_short"


@dataclass
class EngineDecision:
    """Unified output of the hybrid engine."""

    signal: SignalType
    regime: str
    confidence: float  # 0.0 to 1.0
    risk_multiplier: float  # 0.0 to 1.0 (position size scaling)
    filter_decision: FilterDecision
    filter_reason: str
    passed_all_filters: bool

    @property
    def is_actionable(self) -> bool:
        return (
            self.passed_all_filters
            and self.confidence > 0.1 # Lowered from 0.3
            and self.signal not in (SignalType.HOLD, SignalType.EXIT)
        )


@dataclass
class RegimeParams:
    """Regime-adaptive parameters for the engine.

    Each regime gets its own risk appetite and signal thresholds.
    """

    trend_threshold: float = 0.4
    max_risk_per_trade_pct: float = 1.0
    confidence_threshold: float = 0.5
    max_position_size_pct: float = 2.0
    use_wider_stops: bool = False

    @classmethod
    def for_regime(cls, regime: str, symbol: str = "", timeframe: str = "H1") -> "RegimeParams":
        """Return appropriate params for the detected market regime, adjusted for asset class and timeframe."""
        # 1. Base Thresholds
        params = cls()

        if regime == "trending":
            params.trend_threshold = 0.1
            params.confidence_threshold = 0.2
        elif regime == "ranging":
            params.trend_threshold = 0.5
            params.confidence_threshold = 0.6
        elif regime == "volatile":
            params.trend_threshold = 0.7
            params.confidence_threshold = 0.7
        else: # analyzesing or unknown
            params.trend_threshold = 0.3
            params.confidence_threshold = 0.4

        # 2. Timeframe-Specific Relaxation
        # Lower timeframes (M1-M30) have smaller price moves per bar.
        # We relax the thresholds proportionally so the AI can actually trigger.
        tf_multipliers = {
            "M1": 0.05,    # Ultra relaxed
            "M5": 0.15,
            "M15": 0.25,
            "M30": 0.4,   # Relaxed by 60%
            "H1": 1.0,    # Baseline
            "H4": 2.0,    # Stricter (needs larger moves)
            "D1": 4.0     # Very strict
        }
        multiplier = tf_multipliers.get(timeframe.upper(), 1.0)
        params.trend_threshold *= multiplier

        # 3. Asset-Specific Multipliers
        # Metals move much more in % than FX. Scale up their thresholds to avoid 'volatile' noise.
        is_metal = any(m in symbol.upper() for m in ["XAU", "XAG", "GOLD", "SILVER"])

        if is_metal:
            # Gold/Silver need ~4x higher thresholds to consider a trend 'strong'
            params.trend_threshold *= 4.0
        else:
            # FX pairs are very quiet; use sensitive thresholds (already multiplied by tf)
            params.trend_threshold *= 0.5

        return params


class HybridDecisionEngine:
    """Main hybrid decision engine.

    Combines HMM-based regime detection with rule-based signal gating
    and regime-adaptive parameter tuning.
    """

    def __init__(
        self,
        hmm_config: Optional[HMMConfig] = None,
        feature_config: Optional[FeatureConfig] = None,
        vol_filter_config: Optional[VolatilityFilterConfig] = None,
        dd_filter_config: Optional[DrawdownFilterConfig] = None,
        signal_fn: Optional[Callable] = None,
    ):
        self.feature_config = feature_config or FeatureConfig()
        self.regime_detector = RegimeHMM(config=hmm_config or HMMConfig())
        self.signal_gate = SignalGate(
            vol_config=vol_filter_config or VolatilityFilterConfig(),
            dd_config=dd_filter_config or DrawdownFilterConfig(),
        )
        self._signal_fn = signal_fn or self._default_signal_logic
        self._trained: bool = False
        self._last_regime: str = "unknown"
        self._regime_history: list[str] = []
        self._decision_history: list[EngineDecision] = []

    def train_regime_model(self, ohlcv: pd.DataFrame) -> "HybridDecisionEngine":
        """Train the HMM regime detector on historical data."""
        self.regime_detector.fit(ohlcv, self.feature_config)
        self._trained = True
        return self

    def load_regime_model(self, path: str) -> "HybridDecisionEngine":
        """Load a pre-trained HMM from disk."""
        self.regime_detector = RegimeHMM.load(path)
        self._trained = True
        return self

    def configure_account(
        self,
        starting_equity: float,
        daily_pnl: float = 0.0,
        total_pnl: float = 0.0,
    ) -> None:
        """Set account-level parameters for drawdown tracking."""
        self.signal_gate.configure(starting_equity, daily_pnl, total_pnl)

    @staticmethod
    def _default_signal_logic(
        close: np.ndarray,
        regime: str,
        regime_params: RegimeParams,
        feature_matrix: np.ndarray,
        feature_names: list[str],
    ) -> tuple[SignalType, float]:
        """Default signal generation logic.

        A simple momentum + volatility breakout strategy that adapts
        to the current regime. This is a reference implementation;
        the engine is designed to accept any Callable for custom strategies.

        Returns:
            (signal_type, confidence)
        """
        if len(close) < 30:
            return SignalType.HOLD, 0.0

        latest_close = close[-1]
        prev_close = close[-2]

        # Price position relative to 20-period SMA
        sma20 = np.mean(close[-20:])
        sma50 = np.mean(close[-50:]) if len(close) >= 50 else sma20

        # Short-term momentum (5-bar ROC)
        if len(close) >= 6:
            roc5 = (close[-1] / close[-6] - 1) * 100
        else:
            roc5 = 0.0

        # Long-term momentum
        if len(close) >= 22:
            roc20 = (close[-1] / close[-22] - 1) * 100
        else:
            roc20 = 0.0

        # ADX from features if available
        adx_val = 0.0
        if "adx" in feature_names:
            adx_idx = feature_names.index("adx")
            adx_val = feature_matrix[-1, adx_idx] if len(feature_matrix) > 0 else 0.0

        # Regime-adaptive decision
        if regime == "trending":
            # Trend-following: stronger weight on longer momentum
            if roc20 > regime_params.trend_threshold and latest_close > sma20:
                confidence = min(1.0, abs(roc20) / 1.0)
                return SignalType.LONG, confidence
            elif roc20 < -regime_params.trend_threshold and latest_close < sma20:
                confidence = min(1.0, abs(roc20) / 1.0)
                return SignalType.SHORT, confidence
            else:
                # Debug log for why trending failed
                # print(f"DEBUG [{regime}]: ROC20={roc20:.4f}, Threshold={regime_params.trend_threshold:.4f}, Close={latest_close:.5f}, SMA20={sma20:.5f}")
                pass

        elif regime == "ranging":
            # Mean-reversion: buy low, sell high within range
            sma = np.mean(close[-20:])
            std = np.std(close[-20:], ddof=1)
            bb_high = sma + 1.5 * std
            bb_low = sma - 1.5 * std

            if latest_close <= bb_low:
                confidence = 0.5
                return SignalType.LONG, confidence
            elif latest_close >= bb_high:
                confidence = 0.5
                return SignalType.SHORT, confidence
            else:
                # print(f"DEBUG [{regime}]: Close={latest_close:.5f}, BB_Low={bb_low:.5f}, BB_High={bb_high:.5f}")
                pass

        elif regime == "volatile":
            # Highly volatile: only trade if very strong signal, else HOLD
            # Look for breakout with confirmation
            if abs(roc5) > regime_params.trend_threshold * 2: # Lowered from 3
                confidence = min(0.6, abs(roc5) / 5.0)  # Lowered denominator
                return SignalType.REDUCED_LONG if roc5 > 0 else SignalType.REDUCED_SHORT, confidence
            else:
                return SignalType.HOLD, 0.0

        # Default: hold with low confidence
        return SignalType.HOLD, 0.0

    def evaluate(
        self,
        ohlcv: pd.DataFrame,
        symbol: str = "",
        timeframe: str = "H1",
        bar_index: int = -1,
        is_friday: bool = False,
        is_monday: bool = False,
    ) -> EngineDecision:
        """Evaluate a complete trading decision for the current bar.

        Pipeline:
          1. Detect market regime via HMM
          2. Get regime-adaptive parameters
          3. Generate signal (strategy logic)
          4. Apply rule-based filters
          5. Return final decision with confidence scaling

        Args:
            ohlcv: Full OHLCV DataFrame (needs at least FeatureConfig.max_lookback bars)
            symbol: Trading pair name
            timeframe: Current evaluation timeframe (e.g., M30, H1)
            bar_index: Index of current bar (-1 = last)
            is_friday: Whether current bar is Friday
            is_monday: Whether current bar is Monday

        Returns:
            EngineDecision with signal, confidence, and filter status
        """
        if not self._trained:
            raise RuntimeError(
                "Regime detector not trained. Call train_regime_model() or load_regime_model() first."
            )

        # 1. Regime detection
        state_ids, state_labels = self.regime_detector.predict(ohlcv)
        regime_probs = self.regime_detector.get_regime_probs(ohlcv)

        current_regime = state_labels[bar_index] if bar_index < len(state_labels) else state_labels[-1]
        self._last_regime = current_regime
        self._regime_history.append(current_regime)

        # 2. Regime-adaptive parameters (Now adjusted for timeframe)
        regime_params = RegimeParams.for_regime(current_regime, symbol, timeframe)

        # 3. Feature matrix for signal logic
        feature_matrix, feature_names = extract_features(ohlcv, self.feature_config)
        close = ohlcv["close"].values.astype(np.float64)

        # 4. Generate signal
        signal, confidence = self._signal_fn(
            close,
            current_regime,
            regime_params,
            feature_matrix,
            feature_names,
        )

        # 5. Apply rule-based filters
        current_row = ohlcv.iloc[bar_index] if bar_index != -1 else ohlcv.iloc[-1]
        prev_close = (
            ohlcv.iloc[bar_index - 1]["close"]
            if bar_index > 0
            else ohlcv.iloc[-2]["close"]
        )

        # Precompute ATR for the filter
        high = ohlcv["high"].values.astype(np.float64)
        low = ohlcv["low"].values.astype(np.float64)
        atr_vals = atr(high, low, close, self.signal_gate.vol_config.atr_period)
        current_atr = atr_vals[bar_index] if bar_index != -1 else atr_vals[-1]
        median_atr = np.nanmedian(atr_vals)

        filter_decision, filter_reason = self.signal_gate.evaluate(
            ohlcv_row=current_row,
            prev_close=prev_close,
            bar_index=bar_index if bar_index >= 0 else len(ohlcv) - 1,
            symbol=symbol,
            is_friday=is_friday,
            is_monday=is_monday,
            atr_value=current_atr,
            median_atr=median_atr,
        )

        passed = filter_decision == FilterDecision.PASS

        # 6. Compute risk multiplier - Fixed to use 1.0 to respect user settings
        risk_multiplier = 1.0

        # Build final decision
        if not passed:
            final_signal = SignalType.HOLD
            # Log why it was blocked if a strategy signal was present
            if signal != SignalType.HOLD:
                print(f"!!! SIGNAL BLOCKED: {symbol} {signal} (Reason: {filter_reason}) !!!")
        else:
            final_signal = signal

        # Force decision log to terminal for better visibility
        if final_signal != SignalType.HOLD:
            print(f"!!! SIGNAL GENERATED: {symbol} {final_signal} (Confidence: {confidence:.2f}) !!!")

        decision = EngineDecision(
            signal=final_signal,
            regime=current_regime,
            confidence=float(confidence),
            risk_multiplier=float(risk_multiplier),
            filter_decision=filter_decision,
            filter_reason=filter_reason,
            passed_all_filters=passed,
        )

        # Update state
        if passed:
            self.signal_gate.count_signal(symbol)
        else:
            bar_idx = bar_index if bar_index >= 0 else len(ohlcv) - 1
            self.signal_gate.register_block(bar_idx, symbol)

        self._decision_history.append(decision)

        return decision

    def get_regime_summary(self) -> dict:
        """Summary of recent regime classifications."""
        if not self._regime_history:
            return {"last_regime": "unknown", "regime_counts": {}}
        counts = {}
        for r in self._regime_history:
            counts[r] = counts.get(r, 0) + 1
        return {
            "last_regime": self._last_regime,
            "regime_counts": counts,
            "total_decisions": len(self._regime_history),
        }

    def get_last_n_decisions(self, n: int = 10) -> list[EngineDecision]:
        """Return the last N engine decisions for analysis."""
        return self._decision_history[-n:]