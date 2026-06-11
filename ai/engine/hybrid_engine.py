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

import logging
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
    confidence_threshold: float = 0.1 # Threshold for actionability

    @property
    def is_actionable(self) -> bool:
        return (
            self.passed_all_filters
            and self.confidence >= self.confidence_threshold
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
    bb_multiplier: float = 1.5 # Multiplier for Bollinger Bands

    @classmethod
    def for_regime(cls, regime: str, symbol: str = "", timeframe: str = "H1", is_aggressive: bool = False) -> "RegimeParams":
        """Return appropriate params for the detected market regime, adjusted dynamically for timeframe."""
        params = cls()

        # Ensure timeframe is a valid string
        tf_str = str(timeframe).upper() if timeframe else "H1"

        # 1. Base Multiplier using "Square Root of Time"
        # Calibrated to H1 (60 mins)
        tf_map = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}
        tf_minutes = tf_map.get(tf_str, 60)

        # Scaling factor: sqrt(selected_minutes / 60)
        scaling_factor = np.sqrt(tf_minutes / 60.0)

        # BB Multiplier scaling: tighter for lower timeframes
        params.bb_multiplier = 1.0 + (np.log10(max(1, tf_minutes)) * 0.3)

        if regime == "trending":
            params.trend_threshold = 0.08 * scaling_factor
            params.confidence_threshold = 0.15 * scaling_factor
        elif regime == "ranging":
            params.trend_threshold = 0.4 * scaling_factor
            params.confidence_threshold = 0.3
        elif regime == "volatile":
            params.trend_threshold = 0.5 * scaling_factor
            params.confidence_threshold = 0.4 * scaling_factor
        else: # analyzing or unknown
            params.trend_threshold = 0.3 * scaling_factor
            params.confidence_threshold = 0.4

        # 2. Aggressive Mode Adjustments (Lower thresholds to capture more opportunities)
        if is_aggressive:
            params.trend_threshold *= 0.6 # 40% lower threshold
            params.confidence_threshold *= 0.7 # 30% lower confidence required
            params.bb_multiplier *= 0.9 # Tighter bands for ranges

        # 3. Asset-Specific Adjustments
        is_metal = any(m in symbol.upper() for m in ["XAU", "XAG", "GOLD", "SILVER"])
        if is_metal:
            # Metals need wider thresholds due to high point-value volatility
            params.trend_threshold *= 1.5
        else:
            # FX pairs are slightly more sensitive
            params.trend_threshold *= 0.8

        return params


class HybridDecisionEngine:
    """Main hybrid decision engine."""

    def __init__(
        self,
        hmm_config: Optional[HMMConfig] = None,
        feature_config: Optional[FeatureConfig] = None,
        vol_filter_config: Optional[VolatilityFilterConfig] = None,
        dd_filter_config: Optional[DrawdownFilterConfig] = None,
        signal_fn: Optional[Callable] = None,
    ):
        self.feature_config = feature_config or FeatureConfig()
        self.hmm_config = hmm_config or HMMConfig()
        self.vol_filter_config = vol_filter_config or VolatilityFilterConfig()
        self.dd_filter_config = dd_filter_config or DrawdownFilterConfig()

        # Symbol-specific detectors and states
        self.detectors: dict[str, RegimeHMM] = {}
        self.signal_gate = SignalGate(
            vol_config=self.vol_filter_config,
            dd_config=self.dd_filter_config,
        )
        self._signal_fn = signal_fn or self._default_signal_logic
        self._trained_symbols: set[str] = set()
        self._last_regime: str = "unknown"
        self._regime_history: list[str] = []
        self._decision_history: list[EngineDecision] = []

    def is_trained(self, symbol: str) -> bool:
        return symbol in self._trained_symbols

    def train_regime_model(self, symbol: str, ohlcv: pd.DataFrame) -> "HybridDecisionEngine":
        """Train a symbol-specific HMM regime detector."""
        detector = RegimeHMM(config=self.hmm_config)
        detector.fit(ohlcv, self.feature_config)
        self.detectors[symbol] = detector
        self._trained_symbols.add(symbol)
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
            # Trend-following: balanced momentum thresholds from original development
            if roc20 > regime_params.trend_threshold and latest_close > sma20:
                confidence = min(1.0, abs(roc20) / 0.5) # Original more sensitive formula
                return SignalType.LONG, confidence
            elif roc20 < -regime_params.trend_threshold and latest_close < sma20:
                confidence = min(1.0, abs(roc20) / 0.5)
                return SignalType.SHORT, confidence
            else:
                # Debug log for why trending failed
                # print(f"DEBUG [{regime}]: ROC20={roc20:.4f}, Threshold={regime_params.trend_threshold:.4f}, Close={latest_close:.5f}, SMA20={sma20:.5f}")
                pass

        elif regime == "ranging":
            # Mean-reversion: use scaled BB bands
            sma = np.mean(close[-20:])
            std = np.std(close[-20:], ddof=1)
            bb_high = sma + regime_params.bb_multiplier * std
            bb_low = sma - regime_params.bb_multiplier * std

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
            # Highly volatile: trade if signal is stronger than normal trend requirement
            if abs(roc5) > regime_params.trend_threshold:
                confidence = min(0.9, abs(roc5) / 1.0) # Increased max confidence
                return SignalType.REDUCED_LONG if roc5 > 0 else SignalType.REDUCED_SHORT, confidence
            else:
                return SignalType.HOLD, 0.0

        # Default: hold with low confidence
        return SignalType.HOLD, 0.0

    def evaluate(
        self,
        ohlcv: pd.DataFrame,
        symbol: str,
        timeframe: str = "H1",
        bar_index: int = -1,
        is_friday: bool = False,
        is_monday: bool = False,
        is_aggressive: bool = False,
    ) -> EngineDecision:
        """Evaluate a complete trading decision for a specific symbol."""
        if not self.is_trained(symbol):
            raise RuntimeError(f"Regime detector for {symbol} not trained.")

        # 1. Regime detection using symbol-specific model
        detector = self.detectors[symbol]
        state_ids, state_labels = detector.predict(ohlcv)
        regime_probs = detector.get_regime_probs(ohlcv)

        current_regime = state_labels[bar_index] if bar_index < len(state_labels) else state_labels[-1]
        self._last_regime = current_regime
        self._regime_history.append(current_regime)

        logging.info(f"[{symbol}] Detected Regime: {current_regime.upper()}")

        # 2. Regime-adaptive parameters (Now adjusted for timeframe and aggression)
        regime_params = RegimeParams.for_regime(current_regime, symbol, timeframe, is_aggressive)

        # 3. Feature matrix for signal logic
        feature_matrix, feature_names = extract_features(ohlcv, self.feature_config)
        close = ohlcv["close"].values.astype(np.float64)

        # 4. Generate signal (Slice data if bar_index is provided to avoid look-ahead bias)
        signal_close = close[:bar_index + 1] if bar_index >= 0 else close
        signal_features = feature_matrix[:bar_index + 1] if bar_index >= 0 else feature_matrix

        try:
            signal, confidence = self._signal_fn(
                signal_close,
                current_regime,
                regime_params,
                signal_features,
                feature_names,
            )
        except Exception as e:
            logging.error(f"[{symbol}] Signal function error: {e}")
            signal, confidence = SignalType.HOLD, 0.0

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
                logging.info(f"!!! SIGNAL BLOCKED: {symbol} {signal} (Reason: {filter_reason}) !!!")
        else:
            final_signal = signal

        # Force decision log to terminal for better visibility
        if final_signal != SignalType.HOLD:
            logging.info(f"!!! SIGNAL GENERATED: {symbol} {final_signal} (Confidence: {confidence:.2f}) !!!")

        decision = EngineDecision(
            signal=final_signal,
            regime=current_regime,
            confidence=float(confidence),
            confidence_threshold=regime_params.confidence_threshold,
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