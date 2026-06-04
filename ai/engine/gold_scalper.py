"""Strategy 4: Gold Scalper (RSI + ADX + Candle Structure).

Strict logic for XAUUSD (Gold) based on:
1. RSI > 60 and above its MA(14)
2. Rising ADX and +DI > -DI
3. Bullish candle structure
4. Dynamic exit on break of previous low
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional, Tuple
import logging
from ..features.indicators import rsi, adx

class SignalType(Enum):
    BUY = "buy"
    EXIT = "exit"
    HOLD = "hold"

@dataclass
class ScalperDecision:
    signal: SignalType
    pair: str
    rsi_val: float
    rsi_ma: float
    adx_val: float
    plus_di: float
    minus_di: float
    regime: str
    reason: str

class GoldScalperStrategy:
    def __init__(self, config: Dict):
        self.config = config
        self.rsi_period = 14
        self.adx_period = 14

    def evaluate(self, symbol: str, df: pd.DataFrame) -> ScalperDecision:
        if len(df) < 50:
            return self._hold(symbol, "Insufficient data")

        # 1. RSI Calculations
        close = df['close'].values.astype(np.float64)
        high = df['high'].values.astype(np.float64)
        low = df['low'].values.astype(np.float64)

        rsi_vals = rsi(close, self.rsi_period)
        # Calculate 14-period SMA of RSI
        rsi_ma = pd.Series(rsi_vals).rolling(window=14).mean().values

        curr_rsi = rsi_vals[-1]
        curr_rsi_ma = rsi_ma[-1]

        # 2. ADX Calculations
        adx_vals = adx(high, low, close, self.adx_period)
        # We need DI+ and DI- (simplified calculation similar to ADX internal DM)
        up = high[1:] - high[:-1]
        down = low[:-1] - low[1:]
        plus_dm = np.where((up > down) & (up > 0), up, 0.0)
        minus_dm = np.where((down > up) & (down > 0), down, 0.0)

        # Smoothing DM for DI
        tr_vals = np.maximum(high[1:] - low[1:], np.maximum(abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1])))
        tr_smooth = pd.Series(tr_vals).rolling(window=self.adx_period).sum().values
        pdm_smooth = pd.Series(plus_dm).rolling(window=self.adx_period).sum().values
        mdm_smooth = pd.Series(minus_dm).rolling(window=self.adx_period).sum().values

        plus_di = (100 * pdm_smooth / tr_smooth)[-1] if tr_smooth[-1] > 0 else 0
        minus_di = (100 * mdm_smooth / tr_smooth)[-1] if tr_smooth[-1] > 0 else 0

        curr_adx = adx_vals[-1]
        prev_adx = adx_vals[-2]

        # 3. Candle Structure
        curr_close = close[-1]
        prev_close = close[-2]
        prev_low = low[-2]

        # ENTRY LOGIC (BUY ONLY)
        # RSI(14) > 60 AND RSI > RSI_MA AND Close > PrevClose AND ADX Rising AND +DI > -DI
        is_rsi_bullish = curr_rsi > 60 and curr_rsi > curr_rsi_ma
        is_candle_bullish = curr_close > prev_close
        is_trend_strong = curr_adx > prev_adx and plus_di > minus_di

        final_signal = SignalType.HOLD
        reason = "Monitoring market structure"

        if is_rsi_bullish and is_candle_bullish and is_trend_strong:
            final_signal = SignalType.BUY
            reason = "Strategy 4: Bullish Breakout Confirmed"

        # EXIT LOGIC (Managed by engine, but provided here as check)
        # CurrentClose < PreviousLow
        if curr_close < prev_low:
            # Note: The engine will check this for open positions
            pass

        return ScalperDecision(
            signal=final_signal,
            pair=symbol,
            rsi_val=round(curr_rsi, 2),
            rsi_ma=round(curr_rsi_ma, 2),
            adx_val=round(curr_adx, 2),
            plus_di=round(plus_di, 2),
            minus_di=round(minus_di, 2),
            regime="Scalping" if is_trend_strong else "Stable",
            reason=reason
        )

    def _hold(self, symbol, reason) -> ScalperDecision:
        return ScalperDecision(
            SignalType.HOLD, symbol, 0, 0, 0, 0, 0, "Wait", reason
        )
