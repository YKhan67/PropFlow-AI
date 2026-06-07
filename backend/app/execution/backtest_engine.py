import logging
import pandas as pd
import numpy as np
from datetime import datetime
from .backtest.hmm_runner import run_hmm_backtest
from .backtest.quant_runner import run_quant_backtest
from .backtest.gold_runner import run_gold_backtest
from .backtest.correlation_runner import run_correlation_backtest

class BacktestEngine:
    def __init__(self, bridge):
        self.bridge = bridge

    def run_backtest(self, strategy_name, symbol_input, timeframe_str, date_from, date_to, risk_config, lot_size=0.1, profit_target=0):
        # 1. Parse Symbols
        symbols = [s.strip().upper() for s in symbol_input.split(",") if s.strip()]
        logging.info(f"Starting Multi-Symbol Dispatcher: {strategy_name} on {symbols}")

        combined_trades = []
        all_ohlcv = []

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

                # 2. DISPATCH TO STRATEGY-SPECIFIC RUNNER
                symbol_trades = []
                if strategy_name == "hybrid_hmm":
                    symbol_trades = run_hmm_backtest(symbol, df, timeframe_str, lot_size, profit_target)
                elif strategy_name == "quant_engine":
                    symbol_trades = run_quant_backtest(symbol, df, lot_size, profit_target, risk_config)
                elif strategy_name == "gold_scalper":
                    symbol_trades = run_gold_backtest(symbol, df, lot_size, profit_target)
                elif strategy_name == "correlation_reversion":
                    return run_correlation_backtest(symbol, df)
                else:
                    logging.error(f"Unknown strategy: {strategy_name}")
                    continue

                combined_trades.extend(symbol_trades)

            except Exception as e:
                logging.error(f"[BACKTEST] Dispatch error for {symbol}: {e}")
                continue

        # 3. Finalize Stats
        if not combined_trades:
            return {"message": "No trades generated for the selected portfolio.", "total_trades": 0, "ohlcv": all_ohlcv}

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
