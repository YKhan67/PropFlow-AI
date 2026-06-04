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

    def run_backtest(self, strategy_name, symbol_input, timeframe_str, date_from, date_to, risk_config, lot_size=0.1, profit_target=0):
        # 1. Parse Symbols (Support Multiple)
        symbols = [s.strip().upper() for s in symbol_input.split(",") if s.strip()]
        logging.info(f"Starting Multi-Symbol Backtest: {strategy_name} on {symbols} with lot size {lot_size}")

        combined_trades = []
        all_ohlcv = [] # For visual playback (primary symbol)

        # 2. Get MT5 Timeframe constant
        tf_map = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 16385, "H4": 16388, "D1": 16408}
        mt5_tf = tf_map.get(timeframe_str, 16385)

        for symbol in symbols:
            try:
                logging.info(f"[BACKTEST] Fetching data for {symbol}...")
                rates = self.bridge.get_market_data_range(symbol, mt5_tf, date_from, date_to)
                if rates is None or len(rates) < 150:
                    logging.warning(f"[BACKTEST] Skipping {symbol}: Insufficient data.")
                    continue

                df = pd.DataFrame.from_records(rates)
                df['time'] = pd.to_datetime(df['time'], unit='s')

                # Keep first symbol's OHLCV for chart playback
                if not all_ohlcv:
                    all_ohlcv = [{"time": int(t.timestamp()), "close": c} for t, c in zip(df['time'], df['close'])]

                # 3. Pre-calculate Strategy Logic
                rsi_vals, rsi_ma, adx_vals, plus_di, minus_di = [], [], [], [], []
                regimes = []

                if strategy_name == "gold_scalper":
                    from ai.features.indicators import rsi, adx
                    close = df['close'].values.astype(np.float64)
                    high = df['high'].values.astype(np.float64)
                    low = df['low'].values.astype(np.float64)
                    rsi_vals = rsi(close, 14)
                    rsi_ma = pd.Series(rsi_vals).rolling(window=14).mean().values
                    adx_vals = adx(high, low, close, 14)
                    up = np.insert(high[1:] - high[:-1], 0, 0)
                    down = np.insert(low[:-1] - low[1:], 0, 0)
                    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
                    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
                    tr = np.maximum(high - low, np.maximum(abs(high - np.roll(close, 1)), abs(low - np.roll(close, 1))))
                    tr_smooth = pd.Series(tr).rolling(window=14).sum().values
                    plus_di = 100 * pd.Series(plus_dm).rolling(window=14).sum().values / tr_smooth
                    minus_di = 100 * pd.Series(minus_dm).rolling(window=14).sum().values / tr_smooth

                elif strategy_name == "hybrid_hmm":
                    strategy = HybridDecisionEngine()
                    strategy.train_regime_model(symbol, df.iloc[:120])
                    detector = strategy.detectors[symbol]
                    _, state_labels = detector.predict(df)
                    pad_len = len(df) - len(state_labels)
                    regimes = ["unknown"] * pad_len + list(state_labels)

                # 4. Simulation Loop for this symbol
                active_trade = None
                time_to_idx = {t: i for i, t in enumerate(df['time'])}

                for i in range(120, len(df)):
                    current_row = df.iloc[i]
                    prev_row = df.iloc[i-1]

                    # EXIT LOGIC
                    if active_trade:
                        exit_now = False
                        curr_diff = (current_row['close'] - active_trade['open_price']) if active_trade['type'] == 'buy' else (active_trade['open_price'] - current_row['close'])

                        if "XAU" in symbol: usd = curr_diff * 100 * lot_size
                        elif "JPY" in symbol: usd = curr_diff * 1000 * lot_size
                        else: usd = curr_diff * 100000 * lot_size

                        if profit_target > 0 and usd >= profit_target: exit_now = True
                        elif strategy_name == "gold_scalper" and current_row['close'] < prev_row['low']: exit_now = True
                        elif strategy_name == "hybrid_hmm" and regimes[i] in ["volatile", "unknown"]: exit_now = True
                        elif strategy_name == "quant_engine" and abs(curr_diff / active_trade['open_price']) > 0.01: exit_now = True

                        if exit_now:
                            active_trade.update({
                                'close_price': current_row['close'],
                                'close_time': current_row['time'],
                                'pnl_usd': usd,
                                'pnl_pips': curr_diff * (100 if "JPY" in symbol else 10000),
                                'close_idx': i # Store actual bar index
                            })
                            combined_trades.append(active_trade)
                            active_trade = None

                    # ENTRY LOGIC
                    if not active_trade:
                        if strategy_name == "gold_scalper":
                            if (rsi_vals[i] > 60 and rsi_vals[i] > rsi_ma[i] and current_row['close'] > prev_row['close'] and adx_vals[i] > adx_vals[i-1] and plus_di[i] > minus_di[i]):
                                active_trade = {'symbol': symbol, 'type': 'buy', 'open_price': current_row['close'], 'open_time': current_row['time'], 'open_idx': i}
                        elif strategy_name == "hybrid_hmm":
                            if regimes[i] == "trending" and current_row['close'] > prev_row['close']:
                                active_trade = {'symbol': symbol, 'type': 'buy', 'open_price': current_row['close'], 'open_time': current_row['time'], 'open_idx': i}
                        elif strategy_name == "quant_engine":
                            # Optimized Quant check (simplified for backtest speed)
                            if regimes[i] == "trending" and current_row['close'] > prev_row['close']:
                                active_trade = {'symbol': symbol, 'type': 'buy', 'open_price': current_row['close'], 'open_time': current_row['time'], 'open_idx': i}

            except Exception as e:
                logging.error(f"[BACKTEST] Error processing {symbol}: {e}")
                continue

        # 5. Finalize Stats
        if not combined_trades:
            return {"message": "No trades generated for the selected portfolio.", "total_trades": 0, "ohlcv": all_ohlcv}

        # Sort trades by time to merge portfolios
        combined_trades.sort(key=lambda x: x['open_time'])
        win_trades_count = len([t for t in combined_trades if t['pnl_usd'] > 0])
        win_rate = (win_trades_count / len(combined_trades) * 100) if combined_trades else 0

        return {
            "strategy": strategy_name,
            "symbol": symbol_input,
            "timeframe": timeframe_str,
            "period": f"{date_from.date()} to {date_to.date()}",
            "total_trades": len(combined_trades),
            "win_rate": round(win_rate, 2),
            "total_pips": round(sum(t['pnl_pips'] for t in combined_trades), 1),
            "total_usd": round(sum(t['pnl_usd'] for t in combined_trades), 2),
            "ohlcv": all_ohlcv,
            "trades": [{
                "time": t['open_time'].strftime("%Y-%m-%d %H:%M"),
                "type": f"{t['symbol']} {t['type'].upper()}",
                "entry": round(t['open_price'], 5),
                "exit": round(t['close_price'], 5),
                "usd": round(t['pnl_usd'], 2),
                "open_idx": t['open_idx'],
                "close_idx": t['close_idx']
            } for t in combined_trades]
        }
