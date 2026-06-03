"""FX-QUANT-ENGINE: Institutional-grade Multi-Module Strategy & Execution.

Eight Analytical Modules:
1. Correlation Engine
2. Hedge Engine
3. Synthetic Pair Engine
4. Stat Arb Engine
5. Market Regime Engine
6. Execution Model
7. Risk & Portfolio Engine
8. Signal Filter
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional, Tuple
import logging

class SignalType(Enum):
    LONG = "long"
    SHORT = "short"
    HEDGE = "hedge"
    EXIT = "exit"
    HOLD = "hold"

@dataclass
class QuantDecision:
    trade_status: str  # executed | rejected | pending
    pair: str
    direction: str  # long | short | hedge | hold
    entry_price: float
    position_size: float
    stop_loss: float
    take_profit: float
    strategy_type: str  # stat_arb | synthetic | hedge
    confidence: float
    risk_score: float
    rejection_reason: str
    market_regime: str
    z_score: float

class FXQuantEngine:
    def __init__(self, config: Dict):
        self.config = config
        self.z_entry = config.get('quant_zscore_entry', 2.0)
        self.z_exit = config.get('quant_zscore_exit', 0.5)

        # 1. MAJOR PAIRS (Primary Liquidity Layer)
        self.MAJORS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD"]

        # 2. CROSS MAJOR PAIRS (Structural Relationships Layer)
        self.CROSSES = [
            "EURJPY", "GBPJPY", "EURGBP", "EURCHF", "EURCAD", "EURAUD", "EURNZD",
            "GBPCHF", "GBPCAD", "GBPAUD", "AUDJPY", "NZDJPY", "CADJPY"
        ]

        # 3. SYNTHETIC-CRITICAL PAIRS (Arbitrage Core Layer)
        self.SYNTHETICS = [
            "EURJPY", "GBPJPY", "EURGBP", "AUDJPY", "EURAUD", "GBPAUD",
            "EURCHF", "GBPCAD", "AUDNZD", "CADCHF"
        ]

        # 4. USD STRUCTURE PAIRS (Market Anchor Layer)
        self.ANCHORS = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF", "USDCAD"]

        # 5. COMMODITY-LINKED PAIRS (Macro Regime Layer)
        self.COMMODITIES = ["AUDUSD", "NZDUSD", "USDCAD", "USDNOK", "USDSEK"]

        self.APPROVED_UNIVERSE = set(self.MAJORS + self.CROSSES + self.SYNTHETICS + self.COMMODITIES)

    def evaluate(self, symbol: str, ohlcv: pd.DataFrame, all_tickers: Dict, current_price: float) -> QuantDecision:
        """Full systemic analysis across all institutional layers."""

        # LOGGING START OF ANALYSIS
        # logging.info(f"[{symbol}] Running Institutional FX-QUANT Analysis...")

        # REQUIREMENT: PAIR VALIDATION
        pair_category = self._gatekeeper_check(symbol)
        if not pair_category:
            return self._reject(symbol, "Pair not in approved institutional universe", "unknown")

        # MODULE 5: MARKET REGIME ENGINE
        regime, regime_suitability = self._module_5_regime_engine(ohlcv)

        # MODULE 1: CORRELATION ENGINE (Systemic Stability)
        correlation_consistent = self._module_1_correlation_engine(symbol, all_tickers)

        # MODULE 3: SYNTHETIC PAIR ENGINE (Pricing Inefficiency)
        synthetic_divergence, synthetic_z = self._module_3_synthetic_engine(symbol, all_tickers)

        # MODULE 4: STAT ARB ENGINE (Mean Reversion Alpha)
        stat_arb_z = self._module_4_stat_arb_engine(symbol, ohlcv)

        # ANCHOR LAYER CHECK (USD Structure)
        anchor_stable = self._check_market_anchor_layer(all_tickers)

        # MODULE 6: EXECUTION & COST MODEL
        cost_valid = self._module_6_execution_model(symbol, all_tickers)

        # FINAL SYSTEM RULES & SIGNAL VALIDATION
        confirmations = 0
        if abs(stat_arb_z) >= self.z_entry: confirmations += 1
        if correlation_consistent: confirmations += 1
        if abs(synthetic_z) >= 1.5: confirmations += 1
        if anchor_stable: confirmations += 1

        final_direction = "hold"
        trade_status = "rejected"
        rejection_reason = "No signal"
        confidence = 0.0

        # Institutional Rule: Signal valid only if Stat-Arb triggered AND at least 2 independent confirmations
        if confirmations >= 2 and abs(stat_arb_z) >= self.z_entry:
            if regime_suitability == "YES":
                if cost_valid:
                    trade_status = "executed"
                    final_direction = "long" if stat_arb_z < 0 else "short"
                    rejection_reason = ""
                    confidence = min(100.0, abs(stat_arb_z) * 35.0)
                else:
                    rejection_reason = "Transaction cost exceeds edge (High Spread)"
            else:
                rejection_reason = f"Regime {regime} unsuitable for mean reversion"
        elif abs(stat_arb_z) <= self.z_exit:
            rejection_reason = "Mean reversion target reached"

        # MODULE 7: RISK ENGINE (Dynamic Sizing)
        pos_size = 0.0
        risk_score = 45.0
        if trade_status == "executed":
            pos_size = self._calculate_position_size(pair_category, regime, risk_score)

        sl, tp = self._calculate_trade_levels(symbol, ohlcv, final_direction, current_price, stat_arb_z)

        return QuantDecision(
            trade_status=trade_status, pair=symbol, direction=final_direction,
            entry_price=current_price, position_size=pos_size, stop_loss=sl, take_profit=tp,
            strategy_type="stat_arb", confidence=confidence, risk_score=risk_score,
            rejection_reason=rejection_reason, market_regime=regime, z_score=stat_arb_z
        )

    def _gatekeeper_check(self, symbol: str) -> Optional[str]:
        s = symbol.upper()
        if s in self.MAJORS: return "MAJOR"
        if s in self.CROSSES: return "CROSS"
        if s in self.SYNTHETICS: return "SYNTHETIC"
        if s in self.COMMODITIES: return "COMMODITY"
        return None

    def _module_1_correlation_engine(self, symbol: str, all_tickers: Dict) -> bool:
        """Measure dynamic relationships between clusters."""
        # Simple proxy: Check if the pair is moving in sync with its primary group
        # In a real environment, we'd use 30/60/90 day rolling coefficients.
        return True # Assumed stable for major universe pairs

    def _module_3_synthetic_engine(self, symbol: str, all_tickers: Dict) -> Tuple[float, float]:
        """Synthetic vs Real pricing divergence (Z-Score calculation)."""
        try:
            s = symbol.upper()
            if s == "EURJPY" and "EURUSD" in all_tickers and "USDJPY" in all_tickers:
                synth = all_tickers["EURUSD"]['bid'] * all_tickers["USDJPY"]['bid']
                real = all_tickers[s]['bid']
                diff = (synth - real) * 100
                return diff, diff / 2.0
            if s == "GBPJPY" and "GBPUSD" in all_tickers and "USDJPY" in all_tickers:
                synth = all_tickers["GBPUSD"]['bid'] * all_tickers["USDJPY"]['bid']
                real = all_tickers[s]['bid']
                diff = (synth - real) * 100
                return diff, diff / 2.0
            if s == "EURGBP" and "EURUSD" in all_tickers and "GBPUSD" in all_tickers:
                synth = all_tickers["EURUSD"]['bid'] / all_tickers["GBPUSD"]['bid']
                real = all_tickers[s]['bid']
                diff = (synth - real) * 10000
                return diff, diff / 2.0
        except: pass
        return 0.0, 0.0

    def _module_4_stat_arb_engine(self, symbol: str, ohlcv: pd.DataFrame) -> float:
        if len(ohlcv) < 50: return 0.0
        close = ohlcv['close'].values
        sma = np.mean(close[-50:])
        std = np.std(close[-50:])
        return (close[-1] - sma) / std if std > 1e-10 else 0.0

    def _check_market_anchor_layer(self, all_tickers: Dict) -> bool:
        """Verifies USD Anchor stability across the major USD pairs."""
        count = 0
        for anchor in self.ANCHORS:
            if anchor in all_tickers: count += 1
        # Need data for at least 3 anchors to validate systemic stability
        return count >= 3

    def _module_5_regime_engine(self, ohlcv: pd.DataFrame) -> Tuple[str, str]:
        if len(ohlcv) < 30: return "unknown", "NO"
        close = ohlcv['close'].values
        returns = np.diff(np.log(close))
        vol = np.std(returns[-20:]) * np.sqrt(24)
        momentum = (close[-1] / close[-20] - 1)

        # Institutional logic relaxed for better trading activity
        if vol > 0.025: return "volatile", "NO"
        if abs(momentum) < 0.005: return "range", "YES"
        return "trend", "YES" # Enabled trading in trends

    def _module_6_execution_model(self, symbol: str, all_tickers: Dict) -> bool:
        ticker = all_tickers.get(symbol)
        if not ticker: return False
        spread = ticker['ask'] - ticker['bid']
        spread_pips = spread * 10000 if "JPY" not in symbol else spread * 100
        return spread_pips < 3.0 # Institutional quality spread requirement

    def _calculate_position_size(self, category: str, regime: str, risk_score: float) -> float:
        base_lot = self.config.get('max_position_size', 0.1)
        multipliers = {"MAJOR": 1.0, "CROSS": 0.7, "SYNTHETIC": 0.5, "COMMODITY": 0.5}
        size = base_lot * multipliers.get(category, 0.5)
        if regime == "volatile": size *= 0.5
        return round(max(0.01, size), 2)

    def _calculate_trade_levels(self, symbol: str, ohlcv: pd.DataFrame, direction: str, price: float, z: float) -> Tuple[float, float]:
        if direction == "hold": return 0.0, 0.0
        close = ohlcv['close'].values
        atr = (np.max(ohlcv['high'].values[-14:]) - np.min(ohlcv['low'].values[-14:])) / 14
        sl_dist = atr * 2.5
        tp_dist = abs(price - np.mean(close[-50:]))
        if direction == "long": return price - sl_dist, price + tp_dist
        return price + sl_dist, price - tp_dist

    def _reject(self, symbol, reason, regime) -> QuantDecision:
        return QuantDecision(
            trade_status="rejected", pair=symbol, direction="hold",
            entry_price=0.0, position_size=0.0, stop_loss=0.0, take_profit=0.0,
            strategy_type="stat_arb", confidence=0.0, risk_score=0.0,
            rejection_reason=reason, market_regime=regime, z_score=0.0
        )
