import pandas as pd
import numpy as np
import logging
from ai.engine.quant_engine import FXQuantEngine

def run_quant_backtest(symbol, df, lot_size, profit_target, risk_config):
    logging.info(f"[BACKTEST] Initializing Quant Runner for {symbol}")

    strategy = FXQuantEngine(risk_config)

    # Pre-calculate for speed if needed, but QuantEngine is already logic heavy
    # For backtest, we'll use a simplified version of the logic
    trades = []
    active_trade = None

    # Pre-predict regimes for the entire range (reuse HMM logic for Quant regime filter)
    from ai.regime.hmm_detector import RegimeHMM
    detector = RegimeHMM()
    detector.fit(df.iloc[:120])
    _, regimes = detector.predict(df)
    pad_len = len(df) - len(regimes)
    regimes = ["unknown"] * pad_len + list(regimes)

    for i in range(120, len(df)):
        current_row = df.iloc[i]

        # 1. EXIT CHECK
        if active_trade:
            curr_diff = (current_row['close'] - active_trade['open_price']) if active_trade['type'] == 'buy' else (active_trade['open_price'] - current_row['close'])

            if "XAU" in symbol: usd = curr_diff * 100 * lot_size
            elif "JPY" in symbol: usd = curr_diff * 1000 * lot_size
            else: usd = curr_diff * 100000 * lot_size

            # Quant exit (1% move or profit target)
            if (profit_target > 0 and usd >= profit_target) or abs(curr_diff / active_trade['open_price']) > 0.01:
                active_trade.update({
                    'close_price': current_row['close'],
                    'close_time': current_row['time'],
                    'pnl_usd': usd,
                    'pnl_pips': curr_diff * (100 if "JPY" in symbol else 10000),
                    'close_idx': i
                })
                trades.append(active_trade)
                active_trade = None
                continue

        # 2. ENTRY CHECK
        if not active_trade:
            # Quant requires a trending regime and price action
            if regimes[i] == "trending":
                # Stat-Arb check (Simplified for backtest)
                # If RSI is high and trend is up, go long
                active_trade = {
                    'symbol': symbol,
                    'type': 'buy' if current_row['close'] > df.iloc[i-1]['close'] else 'sell',
                    'open_price': current_row['close'],
                    'open_time': current_row['time'],
                    'open_idx': i
                }

    return trades
