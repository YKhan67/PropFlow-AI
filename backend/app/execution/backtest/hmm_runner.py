import pandas as pd
import numpy as np
import logging
from ai.engine.hybrid_engine import HybridDecisionEngine

def run_hmm_backtest(symbol, df, timeframe_str, lot_size, profit_target):
    logging.info(f"[BACKTEST] Running Authentic HMM Simulation for {symbol}")

    # 1. PRE-CALCULATE INDICATORS (Vectorized for Speed)
    # We do this once for the whole DF to avoid O(N^2) in the loop
    from ai.features.indicators import rsi, adx
    close = df['close'].values.astype(np.float64)
    low = df['low'].values.astype(np.float64)

    # Simple Technicals used in _default_signal_logic
    sma20 = df['close'].rolling(window=20).mean().values
    roc20 = df['close'].pct_change(periods=20).values * 100

    # HMM Regime Prediction (Pre-calculated for speed)
    # This matches the AI's "Brain" exactly. We train on a larger window
    # to ensure the model captures enough market variety for labeling.
    strategy = HybridDecisionEngine()
    train_size = min(300, len(df) // 3)
    strategy.train_regime_model(symbol, df.iloc[:train_size])
    detector = strategy.detectors[symbol]
    _, state_labels = detector.predict(df)
    pad_len = len(df) - len(state_labels)
    regimes = ["unknown"] * pad_len + list(state_labels)

    # 2. Thresholds (Synced with hybrid_engine.py)
    tf_multipliers = {"M1": 0.05, "M5": 0.15, "M15": 0.25, "M30": 0.4, "H1": 1.0, "H4": 2.0, "D1": 4.0}
    tf_mult = tf_multipliers.get(timeframe_str.upper(), 1.0)

    # In backtest, we use the raw threshold for higher activity
    # A value of 0.1 means 0.1% change needed over 20 bars.
    effective_threshold = 0.1 * tf_mult

    trades = []
    active_trade = None

    # 3. SIMULATION LOOP (O(N))
    for i in range(train_size, len(df)):
        current_close = close[i]
        current_regime = regimes[i]

        # --- EXIT CHECK ---
        if active_trade:
            price_diff = (current_close - active_trade['open_price']) if active_trade['type'] == 'buy' else (active_trade['open_price'] - current_close)

            # PnL Calculation (Normalized for Asset Class)
            if "XAU" in symbol or "GOLD" in symbol: usd = price_diff * 100 * lot_size
            elif "JPY" in symbol: usd = price_diff * 1000 * lot_size
            else: usd = price_diff * 100000 * lot_size

            # Exit on Profit Target OR Regime Change to Volatile/Unknown
            exit_triggered = False
            if profit_target > 0 and usd >= profit_target: exit_triggered = True
            elif current_regime in ["volatile", "unknown"]: exit_triggered = True

            if exit_triggered:
                active_trade.update({
                    'close_price': current_close, 'close_time': df.iloc[i]['time'],
                    'pnl_usd': usd, 'pnl_pips': price_diff * (100 if "JPY" in symbol else 10000),
                    'close_idx': i
                })
                trades.append(active_trade)
                active_trade = None
                continue

        # --- ENTRY CHECK ---
        if not active_trade:
            if current_regime == "trending":
                # BUY: ROC20 > Threshold and Price > SMA20
                if roc20[i] > effective_threshold and current_close > sma20[i]:
                    active_trade = {
                        'symbol': symbol, 'type': 'buy',
                        'open_price': current_close, 'open_time': df.iloc[i]['time'],
                        'open_idx': i
                    }
                # SELL: ROC20 < -Threshold and Price < SMA20
                elif roc20[i] < -effective_threshold and current_close < sma20[i]:
                    active_trade = {
                        'symbol': symbol, 'type': 'sell',
                        'open_price': current_close, 'open_time': df.iloc[i]['time'],
                        'open_idx': i
                    }

    return trades
