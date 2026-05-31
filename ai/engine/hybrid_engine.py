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
            and self.confidence > 0.3
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
    def for_regime(cls, regime: str) -> "RegimeParams":
        """Return appropriate params for the detected market regime."""
        if regime == "trending":
            return cls(
                trend_threshold=0.3,      # Lower threshold → more signals
                max_risk_per_trade_pct=1.5,  # Higher risk appetite
                confidence_threshold=0.4,
                max_position_size_pct=2.0,
                use_wider_stops=False,
            )
        elif regime == "ranging":
            return cls(
                trend_threshold=0.5,      # Higher threshold → fewer signals
                max_risk_per_trade_pct=0.75,  # Lower risk
                confidence_threshold=0.6,  # Higher confidence needed
                max_position_size_pct=1.0,
                use_wider_stops=False,
            )
        elif regime == "volatile":
            return cls(
                trend_threshold=0.7,      # Very high threshold
                max_risk_per_trade_pct=0.5,   # Minimal risk
                confidence_threshold=0.7,  # Strong conviction only
                max_position_size_pct=0.5,    # Tiny positions
                use_wider_stops=True,      # Wider stops to avoid noise
            )
        else:
            return cls()  # Default conservative


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
                confidence = min(1.0, abs(roc20) / 5.0)
                return SignalType.LONG, confidence
            elif roc20 < -regime_params.trend_threshold and latest_close < sma20:
                confidence = min(1.0, abs(roc20) / 5.0)
                return SignalType.SHORT, confidence

        elif regime == "ranging":
            # Mean-reversion: buy low, sell high within range
            bb_high = np.mean(close[-20:]) + 2 * np.std(close[-20:], ddof=1)
            bb_low = np.mean(close[-20:]) - 2 * np.std(close[-20:], ddof=1)

            if latest_close <= bb_low and roc5 > 0:
                confidence = min(1.0, (bb_low - latest_close) / (bb_high - bb_low + 1e-10))
                return SignalType.LONG, confidence
            elif latest_close >= bb_high and roc5 < 0:
                confidence = min(1.0, (latest_close - bb_high) / (bb_high - bb_low + 1e-10))
                return SignalType.SHORT, confidence

        elif regime == "volatile":
            # Highly volatile: only trade if very strong signal, else HOLD
            # Look for breakout with confirmation
            if roc5 > regime_params.trend_threshold * 3 and adx_val > 25:
                confidence = min(0.6, abs(roc5) / 10.0)  # Cap confidence
                return SignalType.REDUCED_LONG, confidence
            elif roc5 < -regime_params.trend_threshold * 3 and adx_val > 25:
                confidence = min(0.6, abs(roc5) / 10.0)
                return SignalType.REDUCED_SHORT, confidence
            else:
                return SignalType.HOLD, 0.0

        # Default: hold with low confidence
        return SignalType.HOLD, 0.0

    def evaluate(
        self,
        ohlcv: pd.DataFrame,
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

        # 2. Regime-adaptive parameters
        regime_params = RegimeParams.for_regime(current_regime)

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
            is_friday=is_friday,
            is_monday=is_monday,
            atr_value=current_atr,
            median_atr=median_atr,
        )

        passed = filter_decision == FilterDecision.PASS

        # 6. Compute risk multiplier
        risk_multiplier = 1.0

        if filter_decision == FilterDecision.REDUCE or filter_decision == FilterDecision.DELAY:
            risk_multiplier = 0.5
        elif filter_decision == FilterDecision.BLOCK:
            risk_multiplier = 0.0

        # Apply regime-based risk adjustment
        risk_multiplier *= min(1.0, regime_params.max_risk_per_trade_pct / 2.0)

        # Apply confidence scaling
        risk_multiplier *= confidence

        # Build final decision
        if not passed and filter_decision == FilterDecision.BLOCK:
            final_signal = SignalType.HOLD
        elif not passed and filter_decision == FilterDecision.DELAY:
            final_signal = SignalType.HOLD
        elif not passed and filter_decision == FilterDecision.REDUCE:
            # Keep signal but reduce size
            if signal == SignalType.LONG:
                final_signal = SignalType.REDUCED_LONG
            elif signal == SignalType.SHORT:
                final_signal = SignalType.REDUCED_SHORT
            else:
                final_signal = signal
        else:
            final_signal = signal

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
            self.signal_gate.count_signal()
        else:
            bar_idx = bar_index if bar_index >= 0 else len(ohlcv) - 1
            self.signal_gate.register_block(bar_idx)

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