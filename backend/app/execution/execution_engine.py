import logging
import time
import datetime
import threading
import pandas as pd
from app.broker.mt5_broker import MT5Bridge
from app.services.risk_engine import RiskManager

# New Modular Strategy Handlers
from .strategies.hmm_handler import HMMHandler
from .strategies.quant_handler import QuantHandler
from .strategies.correlation_handler import CorrelationHandler
from .strategies.gold_handler import GoldHandler

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

        # High-res 5s price buffer for charts
        self.price_history_5s = {}
        self._last_5s_update = 0

        # real-time baskets for Strategy 3
        self.active_baskets = [] # [{'pair_a': str, 'pair_b': str, 'tickets': [int, int]}]

        self.tf_map = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 16385, "H4": 16388, "D1": 16408}
        self.mt5_timeframe = self.tf_map.get(timeframe, 16385)

        self._stop_event = threading.Event()
        self._initialized = False

        # Initialize Modular Strategy Handlers
        self.hmm_handler = HMMHandler(self.risk_manager)
        self.quant_handler = QuantHandler(self.risk_manager)
        self.corr_handler = CorrelationHandler(self.risk_manager)
        self.gold_handler = GoldHandler(self.risk_manager)

        # Start background sync
        self.sync_thread = threading.Thread(target=self._data_sync_loop, daemon=True)
        self.sync_thread.start()

    def _data_sync_loop(self):
        """High-speed monitor for Profit Targets and Market Data."""
        logging.info("Ultra-High Speed Monitoring Activated.")
        last_slow_update = 0

        while not self._stop_event.is_set():
            # Periodic initialization check if bridge is not connected
            if not self._initialized:
                logging.info("Attempting MT5 Bridge initialization...")
                if self.bridge.initialize():
                    self._initialized = True
                    logging.info("MT5 Bridge initialized successfully.")
                else:
                    logging.warning(f"MT5 Bridge initialization failed: {self.bridge.last_error}. Retrying in 5s...")
                    # Interruptible sleep
                    for _ in range(50):
                        if self._stop_event.is_set(): break
                        time.sleep(0.1)
                    continue

            try:
                # --- PHASE 1: FAST (PnL check only if trades are active) ---
                if self.active_trades and self.running:
                    current_pnl = self.calculate_total_pnl()
                    target_profit = self.risk_manager.config.get('global_take_profit', 0)
                    if target_profit > 0 and current_pnl >= target_profit:
                        logging.info(f"!!! TARGET HIT: ${current_pnl:.2f}. Executing Instant Close All !!!")
                        self.close_all_trades()
                        # Immediately refresh active trades from MT5 to prevent loop sticking
                        self.active_trades = self.bridge.get_open_positions()
                        time.sleep(2) # Give MT5 time to process all closures
                        continue

                # --- PHASE 2: NORMAL SPEED (Market Data & Strategy - 1s intervals) ---
                now = time.time()
                if now - last_slow_update >= 1.0:
                    last_slow_update = now

                    # Update Account & Positions once per second
                    self.active_trades = self.bridge.get_open_positions()
                    self.account_cache = self.bridge.get_account_info()

                    # Only fetch info for active symbols and core majors to save bandwidth/CPU
                    target_symbols = list(set(self.symbols + ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]))
                    for symbol in target_symbols:
                        ticker = self.bridge.get_symbol_info(symbol)
                        if ticker:
                            with self.data_lock:
                                self.market_scanner[symbol] = ticker
                                # 5s Chart Buffer (optimized to avoid excessive lock duration)
                                if now - self._last_5s_update >= 5:
                                    if symbol not in self.price_history_5s: self.price_history_5s[symbol] = []
                                    self.price_history_5s[symbol].append({"time": int(now), "close": ticker['bid']})
                                    if len(self.price_history_5s[symbol]) > 100: self.price_history_5s[symbol].pop(0)

                    if now - self._last_5s_update >= 5: self._last_5s_update = now

                    # Update Risk & History
                    new_equity = self.account_cache.get("equity", self.risk_manager.starting_balance)
                    self.risk_manager.update_equity(new_equity)
                    self.equity_history.append({"time": now, "equity": new_equity})
                    if len(self.equity_history) > 100: self.equity_history.pop(0)

                    # 3. Strategy Evaluation & Regime Detection
                    # We run this always so the dashboard/logs stay updated,
                    # but the actual trade execution happens inside _evaluate_active_strategy
                    # only if self.running is True.
                    if self.symbols:
                        if self._current_symbol_idx >= len(self.symbols): self._current_symbol_idx = 0
                        target_symbol = self.symbols[self._current_symbol_idx]
                        self._evaluate_active_strategy(target_symbol)
                        self._current_symbol_idx = (self._current_symbol_idx + 1) % len(self.symbols)

            except Exception as e:
                logging.error(f"Sync Loop Error: {e}")
            time.sleep(0.1)

    def _evaluate_active_strategy(self, symbol):
        """Routing logic to modular handlers."""
        active = self.risk_manager.config.get('active_strategy', 'hybrid_hmm')

        # Strategy 3: Correlation (Evaluates all symbols at once)
        if active == "correlation_reversion":
            if symbol != self.symbols[0]: return # Only run once per full loop

            basket_signals, statuses = self.corr_handler.evaluate(self.symbols, self.bridge, self.mt5_timeframe, self.timeframe_str)

            with self.data_lock:
                for s, st in statuses.items(): self.symbol_regimes[s] = st

            # 1. Manage Existing Baskets (Exit Check)
            active_tickets = [t['id'] for t in self.active_trades]
            remaining_baskets = []
            for basket in self.active_baskets:
                # If any leg is missing from active trades, close the whole basket
                if not all(tick in active_tickets for tick in basket['tickets']):
                    logging.info(f"!!! Correlation Basket Leg Missing. Closing entire basket {basket['pair_a']}/{basket['pair_b']} !!!")
                    for tick in basket['tickets']:
                        if tick in active_tickets: self.bridge.close_position(tick)
                    continue

                # Check if divergence resolved (Normalized status)
                p1_status = statuses.get(basket['pair_a'], "Neutral")
                p2_status = statuses.get(basket['pair_b'], "Neutral")

                if p1_status in ["Neutral", "Correlated"] and p2_status in ["Neutral", "Correlated"]:
                    logging.info(f"!!! Correlation Normalized for {basket['pair_a']}/{basket['pair_b']}. Closing Basket. !!!")
                    for tick in basket['tickets']: self.bridge.close_position(tick)
                    continue

                remaining_baskets.append(basket)
            self.active_baskets = remaining_baskets

            # 2. Entry Check for New Baskets
            for b_sig in basket_signals:
                existing = any(b['pair_a'] == b_sig['pair_a'] and b['pair_b'] == b_sig['pair_b'] for b in self.active_baskets)
                if not existing:
                    logging.info(f"!!! Opening Correlation Basket: {b_sig['pair_a']} & {b_sig['pair_b']} !!!")
                    tickets = []
                    for trade in b_sig['trades']:
                        res = self._execute_signal_sync(trade)
                        if res and res.get('order'):
                            tickets.append(res['order'])

                    if len(tickets) == 2:
                        self.active_baskets.append({'pair_a': b_sig['pair_a'], 'pair_b': b_sig['pair_b'], 'tickets': tickets})
                    else:
                        # Failed to open both legs, close any that did open
                        for t in tickets: self.bridge.close_position(t)
            return

        # 1. Fetch Market History (Increased to 500 for better M30/H1 context)
        data = self.bridge.get_market_data(symbol, timeframe=self.mt5_timeframe, count=500)
        if data is None or len(data) == 0:
            logging.warning(f"[{symbol}] Failed to fetch market data from MT5.")
            return

        logging.info(f"[{symbol}] Processing {len(data)} bars for strategy evaluation.")

        signal = None
        regime = "analyzing..."

        if active == "hybrid_hmm":
            signal, regime = self.hmm_handler.evaluate(symbol, data, self.timeframe_str)
        elif active == "quant_engine":
            signal, regime = self.quant_handler.evaluate(symbol, data, self.market_scanner)
        elif active == "gold_scalper":
            signal, regime = self.gold_handler.evaluate(symbol, data, self.active_trades, self.bridge)

        # Update dashboard state
        with self.data_lock:
            self.symbol_regimes[symbol] = regime

        # Execute if signal found AND engine is running
        if signal:
            if self.running:
                logging.info(f"!!! {active.upper()} SIGNAL APPROVED: {symbol} {signal['reason']} !!!")
                self._execute_signal(signal)
            else:
                logging.info(f"[{symbol}] Signal detected ({signal['reason']}) but engine is in PASSIVE mode (Stopped).")

    def _execute_signal(self, signal):
        status, validated = self.risk_manager.check_order(signal, active_trades_count=len(self.active_trades))
        if status in ['approved', 'modified']:
            result = self.bridge.place_order(symbol=validated['symbol'], order_type=validated['type'], volume=validated['volume'])
            if result and result.get('retcode') == 10009:
                self.risk_manager.register_trade(validated['symbol'])
            return result
        return None

    def _execute_signal_sync(self, signal):
        """Synchronous execution helper for baskets."""
        status, validated = self.risk_manager.check_order(signal, active_trades_count=len(self.active_trades))
        if status in ['approved', 'modified']:
            return self.bridge.place_order(symbol=validated['symbol'], order_type=validated['type'], volume=validated['volume'])
        return None

    def start(self):
        self.running = True
        logging.info("Trading Engine Activated.")

    def stop(self):
        self.running = False
        logging.info("Trading Engine Deactivated.")

    def shutdown(self):
        """Complete shutdown of the engine and bridge."""
        logging.info("Shutting down Execution Engine...")
        self.stop()
        self._stop_event.set()

        # The sync_thread is a daemon, so we don't strictly need to wait for it.
        # But we try to give it a moment to finish its current loop iteration.
        if hasattr(self, 'sync_thread') and self.sync_thread.is_alive():
            logging.info("Signaling sync thread to stop...")
            # We don't join() anymore as it might be blocked in a C-extension call
            # that join() can't interrupt on some systems.

        logging.info("Calling Bridge shutdown...")
        self.bridge.shutdown()
        logging.info("Execution Engine shutdown sequence complete.")

    def set_timeframe(self, tf_str):
        self.timeframe_str = tf_str
        self.mt5_timeframe = self.tf_map.get(tf_str, 16385)
        self.hmm_handler.ai._trained_symbols = set() # Reset HMM on TF change
        logging.info(f"Engine timeframe updated to {tf_str}")

    def get_account_info(self):
        return self.account_cache if self.account_cache else self.bridge.get_account_info()

    def close_all_trades(self):
        for pos in self.active_trades: self.bridge.close_position(pos['id'])
        return True

    def calculate_total_pnl(self):
        return sum(t.get('profit', 0) + t.get('commission', 0) + t.get('swap', 0) for t in self.active_trades)

    def get_active_trades(self): return self.active_trades

    def get_market_scanner(self):
        with self.data_lock:
            symbol_pnl = {}
            for t in self.active_trades:
                sym = t['symbol']
                net = t.get('profit', 0) + t.get('commission', 0) + t.get('swap', 0)
                symbol_pnl[sym] = symbol_pnl.get(sym, 0) + net

            enriched = []
            for symbol in self.symbols:
                data = self.market_scanner.get(symbol)
                if not data: continue
                enriched.append({
                    "symbol": symbol, "bid": data['bid'], "ask": data['ask'],
                    "change": data.get('change', 0.0), "trend": data.get('trend', "neutral"),
                    "regime": self.symbol_regimes.get(symbol, "analyzing..."),
                    "pnl": round(symbol_pnl.get(symbol, 0), 2)
                })
            return enriched

    def get_equity_history(self):
        return [{"timestamp": p['time'] * 1000, "equity": p['equity']} for p in self.equity_history]

    def get_market_regime(self):
        active = self.risk_manager.config.get('active_strategy', 'hybrid_hmm')
        names = {"hybrid_hmm": "Hybrid AI", "quant_engine": "FX-QUANT", "gold_scalper": "Gold Scalper", "correlation_reversion": "Correlation"}
        return names.get(active, "Unknown")
