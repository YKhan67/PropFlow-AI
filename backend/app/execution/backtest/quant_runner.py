import pandas as pd
import numpy as np
import logging
from ai.engine.quant_engine import FXQuantEngine

def run_quant_backtest(symbol, df, lot_size, profit_target, risk_config):
    logging.info(f"[BACKTEST] Running Optimized Quant for {symbol}")

    strategy = FXQuantEngine(risk_config)

    # 1. Pre-predict regimes efficiently
    from ai.regime.hmm_detector import RegimeHMM
    detector = RegimeHMM()
    try:
        detector.fit(df.iloc[:150])
        _, state_labels = detector.predict(df)
        pad = len(df) - len(state_labels)
        regimes = ["unknown"] * pad + list(state_labels)
    except:
        regimes = ["unknown"] * len(df)

    # 2. Pre-calculate Statistics (SMA/STD)
    close = df['close'].values.astype(float)
    sma50 = df['close'].rolling(window=50).mean().values
    std50 = df['close'].rolling(window=50).std().values
    zscores = (close - sma50) / np.maximum(std50, 1e-10)

    trades = []
    active_trade = None

    for i in range(150, len(df)):
        current_close = close[i]
        current_regime = regimes[i]
        z = zscores[i]

        # 3. EXIT CHECK
        if active_trade:
            price_diff = (current_close - active_trade['open_price']) if active_trade['type'] == 'buy' else (active_trade['open_price'] - current_close)
            if "XAU" in symbol: usd = price_diff * 100 * lot_size
            elif "JPY" in symbol: usd = price_diff * 1000 * lot_size
            else: usd = price_diff * 100000 * lot_size

            # Target reached or 1% stop
            if (profit_target > 0 and usd >= profit_target) or abs(z) < 0.5 or abs(price_diff / active_trade['open_price']) > 0.01:
                active_trade.update({
                    'close_price': current_close, 'close_time': df.iloc[i]['time'],
                    'pnl_usd': usd, 'pnl_pips': price_diff * (100 if "JPY" in symbol else 10000),
                    'close_idx': i
                })
                trades.append(active_trade)
                active_trade = None
                continue

        # 4. ENTRY CHECK
        if not active_trade:
            if current_regime in ["trending", "range"]:
                # Buy if oversold (Z < -2), Sell if overbought (Z > 2)
                if z < -2.0:
                    active_trade = {'symbol': symbol, 'type': 'buy', 'open_price': current_close, 'open_time': df.iloc[i]['time'], 'open_idx': i}
                elif z > 2.0:
                    active_trade = {'symbol': symbol, 'type': 'sell', 'open_price': current_close, 'open_time': df.iloc[i]['time'], 'open_idx': i}

    return trades
