import logging
import time
import datetime
import threading
import pandas as pd
from app.broker.mt5_broker import MT5Bridge
from app.services.risk_engine import RiskManager

try:
    from ai.engine.hybrid_engine import HybridDecisionEngine, SignalType as HybridSignalType
    from ai.engine.quant_engine import FXQuantEngine, SignalType as QuantSignalType
    from ai.engine.correlation_engine import CorrelationStrategy
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    logging.warning("AI modules not found. Using dummy signals.")

class ExecutionEngine:
    def __init__(self, symbols, risk_config, mt5_login=None, mt5_password=None, mt5_server=None, timeframe="H1"):
        self.symbols = symbols
        self.bridge = MT5Bridge(login=mt5_login, password=mt5_password, server=mt5_server)
        self.risk_manager = RiskManager(risk_config)
        self.running = False
        self.active_trades = []
        self.market_scanner = {}
        self.equity_history = []
        self.symbol_regimes = {}
        self.account_cache = {}
        self._current_symbol_idx = 0
        self.timeframe_str = timeframe
        self.data_lock = threading.Lock()

        # Mapping timeframe strings to MT5 constants
        self.tf_map = {
            "M1": 1, "M5": 5, "M15": 15, "M30": 30,
            "H1": 16385, "H4": 16388, "D1": 16408
        }
        self.mt5_timeframe = self.tf_map.get(timeframe, 16385)

        # Initialize bridge
        self.bridge.initialize()

        if AI_AVAILABLE:
            logging.info("AI Decision Engines successfully loaded.")
            self.ai_hmm = HybridDecisionEngine()
            self.ai_hmm._trained = False

            # Sync initial settings for HMM
            self.ai_hmm.signal_gate.dd_config.min_time_between_trades_minutes = risk_config.get('min_time_between_trades', 5)
            self.ai_hmm.signal_gate.dd_config.daily_drawdown_limit_pct = risk_config.get('max_daily_drawdown', 0.05) * 100
            self.ai_hmm.signal_gate.dd_config.total_drawdown_limit_pct = risk_config.get('max_total_drawdown', 0.10) * 100

            self.ai_quant = FXQuantEngine(risk_config)
            self.ai_corr = CorrelationStrategy(risk_config)
        else:
            self.ai_hmm = None
            self.ai_quant = None
            self.ai_corr = None

        # Start the background data synchronizer
        self.sync_thread = threading.Thread(target=self._data_sync_loop, daemon=True)
        self.sync_thread.start()

    def _data_sync_loop(self):
        """Sequential but efficient loop for MT5 data."""
        logging.info("Background Sync Loop Started.")
        while True:
            try:
                # 1. Update Market Prices (User Symbols + Institutional Anchors)
                target_symbols = list(set(
                    self.symbols +
                    ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD", "NZDUSD", "USDCHF", "XAUUSD", "XAGUSD"]
                ))

                for symbol in target_symbols:
                    ticker = self.bridge.get_symbol_info(symbol)
                    if ticker:
                        with self.data_lock:
                            self.market_scanner[symbol] = ticker

                # 2. Update Account & Trades (Fast)
                self.active_trades = self.bridge.get_open_positions()
                self.account_cache = self.bridge.get_account_info()

                # 3. Update History & Risk
                current_pnl = self.calculate_total_pnl()
                new_equity = self.account_cache.get("equity", self.risk_manager.starting_balance)
                self.risk_manager.update_equity(new_equity)

                self.equity_history.append({"time": time.time(), "equity": new_equity})
                if len(self.equity_history) > 100:
                    self.equity_history.pop(0)

                # 4. Strategy Evaluation (One symbol per loop to prevent lag)
                if self.running and self.symbols:
                    # Safety check: ensure index is within range of the current symbols list
                    if self._current_symbol_idx >= len(self.symbols):
                        self._current_symbol_idx = 0

                    target_symbol = self.symbols[self._current_symbol_idx]
                    self._evaluate_symbol_strategy(target_symbol)

                    # Also evaluate group-based strategies (Strategy 3)
                    self._evaluate_all_symbols_strategy()

                    self._current_symbol_idx = (self._current_symbol_idx + 1) % len(self.symbols)

                # 5. Check Basket Exit
                if self.running:
                    target_profit = self.risk_manager.config.get('global_take_profit', 0)
                    if target_profit > 0 and current_pnl >= target_profit:
                        logging.info(f"Global Profit Target Reached (${current_pnl:.2f}).")
                        self.close_all_trades()

            except Exception as e:
                logging.error(f"Sync Loop Error: {e}")

            time.sleep(1)

    def _evaluate_symbol_strategy(self, symbol):
        """Strategy logic routing."""
        data = self.bridge.get_market_data(symbol, timeframe=self.mt5_timeframe, count=250)
        if data is not None and len(data) > 0:
            active_strategy = self.risk_manager.config.get('active_strategy', 'hybrid_hmm')

            if active_strategy == "hybrid_hmm" and self.ai_hmm:
                self._evaluate_hmm_strategy(symbol, data)
            elif active_strategy == "quant_engine" and self.ai_quant:
                self._evaluate_quant_strategy(symbol, data)
            elif active_strategy == "correlation_reversion" and self.ai_corr:
                # We'll evaluate all symbols at once for correlation in the main loop instead
                pass

    def _evaluate_all_symbols_strategy(self):
        """Logic for strategies that require analyzing multiple symbols together."""
        active_strategy = self.risk_manager.config.get('active_strategy', 'hybrid_hmm')
        if active_strategy == "correlation_reversion" and self.ai_corr:
            self._evaluate_correlation_strategy()

    def _evaluate_correlation_strategy(self):
        try:
            # 1. Gather data for all symbols
            all_data = {}
            for sym in self.symbols:
                data = self.bridge.get_market_data(sym, timeframe=self.mt5_timeframe, count=100)
                if data is not None and len(data) > 0:
                    logging.info(f"[{sym}] Data retrieved (100 bars) for Correlation.")
                    all_data[sym] = pd.DataFrame.from_records(data)
                else:
                    logging.warning(f"[{sym}] Failed to retrieve Correlation data. Is it in Market Watch?")

            # 2. Evaluate
            if not all_data:
                return
            decisions, statuses = self.ai_corr.evaluate(all_data, timeframe=self.timeframe_str)

            # Update Dashboard status tags
            with self.data_lock:
                # Update statuses instead of clearing everything to prevent UI flicker
                for sym, status in statuses.items():
                    self.symbol_regimes[sym] = status

                # Tag anything not in the current active analysis list
                for sym in self.symbols:
                    if sym not in statuses:
                        self.symbol_regimes[sym] = "Wait Data..."

            # 3. Process Decisions (Baskets)
            for d in decisions:
                logging.info(f"!!! Correlation Signal: {d.reason} (Coef: {d.coefficient:.2f}) !!!")

                # Check if we already have a trade in this pair combo
                existing = any(t['symbol'] in [d.pair_a, d.pair_b] for t in self.active_trades)
                if not existing:
                    max_pos = self.risk_manager.config.get('max_position_size', 0.1)
                    # Execute synchronized basket
                    for sig in d.signals:
                        signal_with_vol = {
                            'symbol': sig['symbol'],
                            'type': sig['type'],
                            'volume': float(max_pos)
                        }
                        self._execute_signal(signal_with_vol)
                    logging.info(f"!!! Correlation Basket Opened: {d.pair_a} & {d.pair_b} !!!")

        except Exception as e:
            logging.error(f"Correlation Strategy Error: {e}")

    def _evaluate_hmm_strategy(self, symbol, data):
        try:
            df = pd.DataFrame.from_records(data)
            if not self.ai_hmm._trained:
                logging.info(f"[{symbol}] Initializing HMM model...")
                self.ai_hmm.train_regime_model(df)

            decision = self.ai_hmm.evaluate(df, symbol=symbol, timeframe=self.timeframe_str)
            with self.data_lock:
                self.symbol_regimes[symbol] = decision.regime

            if decision.signal != HybridSignalType.HOLD:
                logging.info(f"[{symbol}] HMM Decision: {decision.signal} (Regime: {decision.regime})")

            if decision.is_actionable:
                max_pos = self.risk_manager.config.get('max_position_size', 0.1)
                signal = {
                    'symbol': symbol,
                    'type': 0 if decision.signal in [HybridSignalType.LONG, HybridSignalType.REDUCED_LONG] else 1,
                    'volume': float(max_pos)
                }
                self._execute_signal(signal)
        except Exception as e:
            logging.error(f"HMM Error [{symbol}]: {e}")

    def _evaluate_quant_strategy(self, symbol, data):
        try:
            df = pd.DataFrame.from_records(data)
            ticker = self.market_scanner.get(symbol)
            current_price = ticker['last'] if ticker else df['close'].iloc[-1]

            # Use the new institutional execution logic
            decision = self.ai_quant.evaluate(symbol, df, self.market_scanner, current_price)

            with self.data_lock:
                self.symbol_regimes[symbol] = decision.market_regime

            if decision.direction != "hold":
                logging.info(f"[{symbol}] institutional Analysis: {decision.direction.upper()} (Regime: {decision.market_regime}) Reason: {decision.rejection_reason}")

            if decision.trade_status == "executed":
                # Convert direction to MT5 types (0=Buy, 1=Sell)
                order_type = 0 if decision.direction == "long" else 1

                signal = {
                    'symbol': symbol,
                    'type': order_type,
                    'volume': decision.position_size,
                    'sl': decision.stop_loss,
                    'tp': decision.take_profit
                }

                logging.info(f"!!! institutional SIGNAL APPROVED: {symbol} {decision.direction.upper()} !!!")
                self._execute_signal(signal)
            else:
                if decision.direction != "hold":
                    logging.info(f"[{symbol}] institutional Trade Filtered: {decision.rejection_reason}")

        except Exception as e:
            logging.error(f"Quant Error [{symbol}]: {e}")

    def _execute_signal(self, signal):
        status, validated_signal = self.risk_manager.check_order(
            signal, active_trades_count=len(self.active_trades)
        )
        if status in ['approved', 'modified']:
            self.bridge.place_order(
                symbol=validated_signal['symbol'],
                order_type=validated_signal['type'],
                volume=validated_signal['volume']
            )

    def start(self):
        logging.info("Trading Engine Activated.")
        self.running = True

    def stop(self):
        self.running = False
        logging.info("Trading Engine Deactivated.")

    def set_timeframe(self, tf_str):
        self.timeframe_str = tf_str
        self.mt5_timeframe = self.tf_map.get(tf_str, 16385)
        if self.ai_hmm:
            self.ai_hmm._trained = False
        logging.info(f"Engine timeframe updated to {tf_str}")

    def get_account_info(self):
        return self.account_cache if self.account_cache else self.bridge.get_account_info()

    def close_all_trades(self):
        logging.info("Closing all active trades...")
        for pos in self.active_trades:
            self.bridge.close_position(pos['id'])
        return True

    def calculate_total_pnl(self):
        return sum(trade.get('profit', 0) + trade.get('commission', 0) + trade.get('swap', 0) for trade in self.active_trades)

    def get_active_trades(self):
        return self.active_trades

    def get_market_scanner(self):
        with self.data_lock:
            # Pre-calculate pnl per symbol from active trades
            symbol_pnl = {}
            for trade in self.active_trades:
                sym = trade['symbol']
                # Net profit = profit + commission + swap
                net = trade.get('profit', 0) + trade.get('commission', 0) + trade.get('swap', 0)
                symbol_pnl[sym] = symbol_pnl.get(sym, 0) + net

            enriched = []
            # ONLY show symbols that belong to the active strategy
            for symbol in self.symbols:
                data = self.market_scanner.get(symbol)
                if not data:
                    continue

                enriched.append({
                    "symbol": symbol,
                    "bid": data['bid'],
                    "ask": data['ask'],
                    "change": data.get('change', 0.0),
                    "trend": data.get('trend', "neutral"),
                    "regime": self.symbol_regimes.get(symbol, "analyzing..."),
                    "pnl": round(symbol_pnl.get(symbol, 0), 2)
                })
            return enriched

    def get_equity_history(self):
        return [{"timestamp": p['time'] * 1000, "equity": p['equity']} for p in self.equity_history]

    def get_market_regime(self):
        # Return the active strategy name for display
        active = self.risk_manager.config.get('active_strategy', 'hybrid_hmm')
        if active == "hybrid_hmm": return "Hybrid AI"
        if active == "quant_engine": return "FX-QUANT"
        return "Correlation Reversion"

    def generate_dummy_signal(self, symbol):
        return None
