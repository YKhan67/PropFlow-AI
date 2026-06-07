import pandas as pd
import numpy as np
import logging
from ai.engine.hybrid_engine import HybridDecisionEngine

def run_hmm_backtest(symbol, df, timeframe_str, lot_size, profit_target):
    logging.info(f"[BACKTEST] Initializing HMM Runner for {symbol}")

    strategy = HybridDecisionEngine()
    # Train once on first 120 bars
    strategy.train_regime_model(symbol, df.iloc[:120])

    # Pre-predict regimes for the entire range
    detector = strategy.detectors[symbol]
    _, state_labels = detector.predict(df)
    pad_len = len(df) - len(state_labels)
    regimes = ["unknown"] * pad_len + list(state_labels)

    trades = []
    active_trade = None

    for i in range(120, len(df)):
        current_row = df.iloc[i]
        prev_row = df.iloc[i-1]

        # 1. EXIT CHECK
        if active_trade:
            exit_now = False
            curr_diff = (current_row['close'] - active_trade['open_price']) if active_trade['type'] == 'buy' else (active_trade['open_price'] - current_row['close'])

            # USD Calc
            if "XAU" in symbol: usd = curr_diff * 100 * lot_size
            elif "JPY" in symbol: usd = curr_diff * 1000 * lot_size
            else: usd = curr_diff * 100000 * lot_size

            # Profit Target or AI Exit (Volatile/Unknown)
            if profit_target > 0 and usd >= profit_target:
                exit_now = True
            elif regimes[i] in ["volatile", "unknown"]:
                exit_now = True

            if exit_now:
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
            if regimes[i] == "trending":
                # Determine direction based on price vs previous close
                if current_row['close'] > prev_row['close']:
                    active_trade = {
                        'symbol': symbol, 'type': 'buy',
                        'open_price': current_row['close'], 'open_time': current_row['time'],
                        'open_idx': i
                    }
                elif current_row['close'] < prev_row['close']:
                    active_trade = {
                        'symbol': symbol, 'type': 'sell',
                        'open_price': current_row['close'], 'open_time': current_row['time'],
                        'open_idx': i
                    }

    return trades
