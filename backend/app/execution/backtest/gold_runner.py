import pandas as pd
import numpy as np
import logging
from ai.features.indicators import rsi, adx

def run_gold_backtest(symbol, df, lot_size, profit_target):
    logging.info(f"[BACKTEST] Initializing Gold Scalper Runner for {symbol}")

    # 1. Pre-calculate indicators (Vectorized for speed)
    close = df['close'].values.astype(np.float64)
    high = df['high'].values.astype(np.float64)
    low = df['low'].values.astype(np.float64)

    rsi_vals = rsi(close, 14)
    rsi_ma = pd.Series(rsi_vals).rolling(window=14).mean().values
    adx_vals = adx(high, low, close, 14)

    # DI+ / DI- Vectorized
    up = np.insert(high[1:] - high[:-1], 0, 0)
    down = np.insert(low[:-1] - low[1:], 0, 0)
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = np.maximum(high - low, np.maximum(abs(high - np.roll(close, 1)), abs(low - np.roll(close, 1))))
    tr_smooth = pd.Series(tr).rolling(window=14).sum().values
    plus_di = 100 * pd.Series(plus_dm).rolling(window=14).sum().values / tr_smooth
    minus_di = 100 * pd.Series(minus_dm).rolling(window=14).sum().values / tr_smooth

    trades = []
    active_trade = None

    for i in range(120, len(df)):
        current_row = df.iloc[i]
        prev_row = df.iloc[i-1]

        # 2. EXIT CHECK
        if active_trade:
            exit_now = False
            # Structural Exit: Current Close < Previous Low
            if current_row['close'] < prev_row['low']:
                exit_now = True

            curr_diff = (current_row['close'] - active_trade['open_price'])
            usd = curr_diff * 100 * lot_size # Always Gold for this runner

            # Profit Target (Optional Override)
            if not exit_now and profit_target > 0 and usd >= profit_target:
                exit_now = True

            if exit_now:
                active_trade.update({
                    'close_price': current_row['close'],
                    'close_time': current_row['time'],
                    'pnl_usd': usd,
                    'pnl_pips': curr_diff * 100,
                    'close_idx': i
                })
                trades.append(active_trade)
                active_trade = None
                continue

        # 3. ENTRY CHECK (BUY ONLY)
        if not active_trade:
            # RSI(14) > 60 AND RSI > RSI_MA AND Close > PrevClose AND ADX Rising AND +DI > -DI
            if (rsi_vals[i] > 60 and rsi_vals[i] > rsi_ma[i] and
                current_row['close'] > prev_row['close'] and
                adx_vals[i] > adx_vals[i-1] and plus_di[i] > minus_di[i]):

                active_trade = {
                    'symbol': symbol, 'type': 'buy',
                    'open_price': current_row['close'], 'open_time': current_row['time'],
                    'open_idx': i
                }

    return trades
