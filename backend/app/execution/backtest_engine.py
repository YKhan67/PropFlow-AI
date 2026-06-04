import logging
import pandas as pd
import numpy as np
from datetime import datetime
from ai.engine.hybrid_engine import HybridDecisionEngine, SignalType as HybridSignalType
from ai.engine.gold_scalper import GoldScalperStrategy, SignalType as GoldSignalType
from ai.engine.quant_engine import FXQuantEngine
from ai.engine.correlation_engine import CorrelationStrategy

class BacktestEngine:
    def __init__(self, bridge):
        self.bridge = bridge

    def run_backtest(self, strategy_name, symbol, timeframe_str, date_from, date_to, risk_config, lot_size=0.1, profit_target=0):
        logging.info(f"Starting backtest: {strategy_name} on {symbol} ({timeframe_str}) from {date_from} to {date_to} with lot size {lot_size}, TP: ${profit_target}")

        # 1. Get MT5 Timeframe constant
        tf_map = {
            "M1": 1, "M5": 5, "M15": 15, "M30": 30,
            "H1": 16385, "H4": 16388, "D1": 16408
        }
        mt5_tf = tf_map.get(timeframe_str, 16385)

        # 2. Fetch Data
        rates = self.bridge.get_market_data_range(symbol, mt5_tf, date_from, date_to)
        if rates is None or len(rates) < 100:
            return {"error": "Insufficient historical data found for this range."}

        df = pd.DataFrame.from_records(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')

        logging.info(f"Data loaded: {len(df)} bars. Pre-calculating indicators...")

        # 3. Initialize Strategy & Pre-calculate (OPTIMIZATION)
        # Instead of calculating every bar, we calculate the whole range once
        if strategy_name == "gold_scalper":
            strategy = GoldScalperStrategy(risk_config)
            # Use the full dataframe to calculate indicators vectorized
            close = df['close'].values.astype(np.float64)
            high = df['high'].values.astype(np.float64)
            low = df['low'].values.astype(np.float64)

            from ai.features.indicators import rsi, adx
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
            pdm_smooth = pd.Series(plus_dm).rolling(window=14).sum().values
            mdm_smooth = pd.Series(minus_dm).rolling(window=14).sum().values
            plus_di = 100 * pdm_smooth / tr_smooth
            minus_di = 100 * mdm_smooth / tr_smooth

        elif strategy_name == "hybrid_hmm":
            strategy = HybridDecisionEngine()
            # Train once on first 100 bars
            strategy.train_regime_model(symbol, df.iloc[:100])
            # Pre-predict regimes for the entire range
            detector = strategy.detectors[symbol]
            _, state_labels = detector.predict(df)
            regimes = state_labels
        else:
            # Fallback for other strategies
            pass

        # 4. Backtest Loop (Now O(N) instead of O(N^2))
        trades = []
        active_trade = None
        start_idx = 100

        logging.info("Starting simulation loop...")

        for i in range(start_idx, len(df)):
            if i % 5000 == 0: # Log progress for very large ranges
                logging.info(f"[BACKTEST] Progress: {int(i/len(df)*100)}%...")

            current_row = df.iloc[i]
            prev_row = df.iloc[i-1]

            # --- EXIT CHECK ---
            if active_trade:
                exit_now = False

                # 1. Structural Exit (Mandatory for Strategy 4)
                if strategy_name == "gold_scalper":
                    # Exit BUY trade when: Current candle close < Previous candle low
                    if current_row['close'] < prev_row['low']:
                        exit_now = True

                # 2. Strategy Profit Target (Optional override if set by user)
                curr_diff = (current_row['close'] - active_trade['open_price']) if active_trade['type'] == 'buy' else (active_trade['open_price'] - current_row['close'])
                if "XAU" in symbol: curr_usd = curr_diff * 100 * lot_size
                else: curr_usd = curr_diff * 100000 * lot_size

                if not exit_now and profit_target > 0 and curr_usd >= profit_target:
                    exit_now = True
                    logging.info(f"Backtest: Fixed Profit Target Reached (${curr_usd:.2f})")

                # 3. Hybrid AI Exit
                if not exit_now and strategy_name == "hybrid_hmm":
                    if regimes[i] == "volatile" or regimes[i] == "unknown":
                        exit_now = True

                if exit_now:
                    active_trade['close_price'] = current_row['close']
                    active_trade['close_time'] = current_row['time']
                    active_trade['pnl_usd'] = curr_usd
                    active_trade['pnl_pips'] = curr_diff * (100 if "JPY" in symbol else 10000)
                    trades.append(active_trade)
                    active_trade = None
                    continue

            # --- ENTRY CHECK ---
            if not active_trade:
                if strategy_name == "gold_scalper":
                    # RSI(14) > 60 AND RSI > RSI_MA AND Close > PrevClose AND ADX Rising AND +DI > -DI
                    if (rsi_vals[i] > 60 and rsi_vals[i] > rsi_ma[i] and
                        current_row['close'] > prev_row['close'] and
                        adx_vals[i] > adx_vals[i-1] and plus_di[i] > minus_di[i]):

                        active_trade = {
                            'symbol': symbol, 'type': 'buy',
                            'open_price': current_row['close'], 'open_time': current_row['time']
                        }
                elif strategy_name == "hybrid_hmm":
                    if regimes[i] == "trending" and current_row['close'] > prev_row['close']:
                         active_trade = {
                            'symbol': symbol, 'type': 'buy',
                            'open_price': current_row['close'], 'open_time': current_row['time']
                        }

        logging.info(f"Backtest complete. Found {len(trades)} trades.")

        # Finalize stats
        if not trades:
            return {"message": "No trades were generated during this period.", "total_trades": 0}

        win_trades = [t for t in trades if t['pnl_pips'] > 0]
        total_pips = sum(t['pnl_pips'] for t in trades)
        total_usd = sum(t['pnl_usd'] for t in trades)

        return {
            "strategy": strategy_name,
            "symbol": symbol,
            "timeframe": timeframe_str,
            "period": f"{date_from.date()} to {date_to.date()}",
            "total_trades": len(trades),
            "win_rate": round(len(win_trades) / len(trades) * 100, 2),
            "total_pips": round(total_pips, 2),
            "total_usd": round(total_usd, 2),
            "ohlcv": [{"time": int(t.timestamp()), "close": c} for t, c in zip(df['time'], df['close'])],
            "trades": [{
                "time": t['open_time'].strftime("%Y-%m-%d %H:%M"),
                "type": t['type'].upper(),
                "entry": round(t['open_price'], 5),
                "exit": round(t['close_price'], 5),
                "pips": round(t['pnl_pips'], 1),
                "usd": round(t['pnl_usd'], 2),
                "open_idx": df.index[df['time'] == t['open_time']][0],
                "close_idx": df.index[df['time'] == t['close_time']][0]
            } for t in trades]
        }
