import pandas as pd
import numpy as np
import logging
from ai.features.indicators import rsi, adx

def run_gold_backtest(symbol, df, lot_size, profit_target):
    logging.info(f"[BACKTEST] Initializing Gold Scalper Runner for {symbol}")

    # Pre-calculate indicators (Vectorized for speed)
    close = df['close'].values.astype(np.float64)
    high = df['high'].values.astype(np.float64)
    low = df['low'].values.astype(np.float64)

    rsi_vals = rsi(close, 14)
    rsi_ma = pd.Series(rsi_vals).rolling(window=14).mean().values
    adx_vals = adx(high, low, close, 14)

    # DI+ / DI- Vectorized (Corrected Shifting)
    close_series = pd.Series(close)
    high_series = pd.Series(high)
    low_series = pd.Series(low)

    up = high_series.diff().fillna(0).values
    down = (-low_series.diff()).fillna(0).values

    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)

    # True Range
    tr1 = high - low
    tr2 = np.abs(high - close_series.shift(1).values)
    tr3 = np.abs(low - close_series.shift(1).values)
    tr = np.nan_to_num(np.maximum(tr1, np.maximum(tr2, tr3)), nan=0.0)

    tr_smooth = pd.Series(tr).rolling(window=14).sum().values
    pdm_smooth = pd.Series(plus_dm).rolling(window=14).sum().values
    mdm_smooth = pd.Series(minus_dm).rolling(window=14).sum().values

    plus_di = 100 * pdm_smooth / np.maximum(tr_smooth, 1e-10)
    minus_di = 100 * mdm_smooth / np.maximum(tr_smooth, 1e-10)

    # Fill NaNs to avoid logical comparison failures
    rsi_vals = np.nan_to_num(rsi_vals, nan=50.0)
    rsi_ma = np.nan_to_num(rsi_ma, nan=50.0)
    adx_vals = np.nan_to_num(adx_vals, nan=0.0)
    plus_di = np.nan_to_num(plus_di, nan=0.0)
    minus_di = np.nan_to_num(minus_di, nan=0.0)

    trades = []
    active_trade = None

    for i in range(120, len(df)):
        # Realistic data access: logic can only see indices up to 'i'
        current_row = df.iloc[i]
        prev_row = df.iloc[i-1]

        # --- EXIT CHECK ---
        if active_trade:
            exit_now = False
            # Structural Exit: Current Close < Previous Low
            if current_row['close'] < prev_row['low']:
                exit_now = True

            curr_diff = (current_row['close'] - active_trade['open_price'])
            usd = curr_diff * 100 * lot_size

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

        # --- ENTRY CHECK --- (Vectorized lookup is safe as indicators were pre-calc'd on rolling windows)
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
