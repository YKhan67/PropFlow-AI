import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
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
                # 1. EXPANDED LOOKBACK (CRITICAL FOR REALISM)
                # To ensure Strategy 1 (HMM) and indicators have enough data to be accurate,
                # we fetch an additional 15 days BEFORE the start date for 'warm-up'
                adjusted_start = date_from - timedelta(days=15)

                logging.info(f"[BACKTEST] Pipeline: {symbol} from {date_from} (Pre-load from {adjusted_start.date()})")

                rates = self.bridge.get_market_data_range(symbol, mt5_tf, adjusted_start, date_to)
                if rates is None or len(rates) < 150:
                    logging.warning(f"[BACKTEST] Skipping {symbol}: Data insufficient.")
                    continue

                # Data structured format check
                df = pd.DataFrame(rates)
                if 'close' not in df.columns:
                    df.columns = ['time', 'open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume'][:len(df.columns)]

                df = df.drop_duplicates(subset=['time']).sort_values('time').reset_index(drop=True)
                df['time'] = pd.to_datetime(df['time'], unit='s')
                for c in ['open', 'high', 'low', 'close']: df[c] = df[c].astype(float)

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
                else:
                    continue

                # FILTER: Only keep trades that opened within the requested range
                # (Prevents trades from the 15-day 'warm-up' period appearing)
                valid_trades = [t for t in symbol_trades if t['open_time'] >= date_from]

                if valid_trades:
                    logging.info(f"[BACKTEST] {symbol}: Found {len(valid_trades)} trades.")
                    combined_trades.extend(valid_trades)
                else:
                    logging.info(f"[BACKTEST] {symbol}: 0 trades generated.")

            except Exception as e:
                import traceback
                logging.error(f"[BACKTEST] Critical Dispatch error for {symbol}: {e}")
                logging.error(traceback.format_exc())
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
                "symbol": t['symbol'],
                "type": f"{t['symbol']} {t['type'].upper()}",
                "entry": round(float(t['open_price']), 5),
                "exit": round(float(t['close_price']), 5),
                "usd": round(float(t['pnl_usd']), 2),
                "open_idx": t.get('open_idx', 0),
                "close_idx": t.get('close_idx', 0)
            } for t in combined_trades]
        }
