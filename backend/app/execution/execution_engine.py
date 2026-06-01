import logging
import time
import datetime
import threading
import pandas as pd
from app.broker.mt5_broker import MT5Bridge
from app.services.risk_engine import RiskManager

try:
    from ai.engine.hybrid_engine import HybridDecisionEngine, SignalType
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    logging.warning("AI module not found. Using dummy signals.")

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
        self.data_lock = threading.Lock() # Added lock to fix the attribute error

        # Mapping timeframe strings to MT5 constants
        self.tf_map = {
            "M1": 1, "M5": 5, "M15": 15, "M30": 30,
            "H1": 16385, "H4": 16388, "D1": 16408
        }
        self.mt5_timeframe = self.tf_map.get(timeframe, 16385)

        # Initialize bridge
        self.bridge.initialize()

        if AI_AVAILABLE:
            logging.info("AI Decision Engine successfully loaded.")
            self.ai_engine = HybridDecisionEngine()
            self.ai_engine._trained = False

            # Sync initial settings
            self.ai_engine.signal_gate.dd_config.min_time_between_trades_minutes = risk_config.get('min_time_between_trades', 5)
            self.ai_engine.signal_gate.dd_config.daily_drawdown_limit_pct = risk_config.get('max_daily_drawdown', 0.05) * 100
            self.ai_engine.signal_gate.dd_config.total_drawdown_limit_pct = risk_config.get('max_total_drawdown', 0.10) * 100
        else:
            self.ai_engine = None

        # Start the background data synchronizer (Dashboard & Risk)
        # This thread handles all MT5 communication to keep the UI fast
        self.sync_thread = threading.Thread(target=self._data_sync_loop, daemon=True)
        self.sync_thread.start()

    def _data_sync_loop(self):
        """Sequential but efficient loop for MT5 data."""
        logging.info("Background Sync Loop Started.")
        while True:
            try:
                # 1. Update Market Prices (Fast)
                ticker_data = {}
                for symbol in self.symbols:
                    ticker = self.bridge.get_symbol_info(symbol)
                    if ticker:
                        ticker_data[symbol] = ticker
                self.market_scanner = ticker_data

                # 2. Update Account & Trades (Fast)
                self.active_trades = self.bridge.get_open_positions()
                self.account_cache = self.bridge.get_account_info()

                # 3. Update History & Risk
                current_pnl = sum(p.get('profit', 0) for p in self.active_trades)
                new_equity = self.account_cache.get("equity", self.risk_manager.starting_balance)
                self.risk_manager.update_equity(new_equity)

                self.equity_history.append({"time": time.time(), "equity": new_equity})
                if len(self.equity_history) > 100:
                    self.equity_history.pop(0)

                # 4. Strategy Evaluation (One symbol per loop to prevent lag)
                if self.running and self.symbols:
                    target_symbol = self.symbols[self._current_symbol_idx]
                    self._evaluate_symbol_strategy(target_symbol)

                    # Move to next symbol for next loop
                    self._current_symbol_idx = (self._current_symbol_idx + 1) % len(self.symbols)

                # 5. Check Basket Exit
                if self.running:
                    target_profit = self.risk_manager.config.get('global_take_profit', 0)
                    if target_profit > 0 and current_pnl >= target_profit:
                        logging.info(f"Global Profit Target Reached (${current_pnl:.2f}).")
                        self.close_all_trades()

            except Exception as e:
                logging.error(f"Sync Loop Error: {e}")

            time.sleep(1) # High-speed refresh for dashboard

    def _evaluate_symbol_strategy(self, symbol):
        """Slow AI logic handled for a single symbol."""
        data = self.bridge.get_market_data(symbol, timeframe=self.mt5_timeframe, count=250)
        if data is not None and len(data) > 0:
            logging.info(f"[{symbol}] Data retrieved ({len(data)} bars). Evaluating AI...")
            if AI_AVAILABLE and self.ai_engine:
                try:
                    df = pd.DataFrame.from_records(data)
                    if not self.ai_engine._trained:
                        logging.info(f"[{symbol}] Initializing AI model...")
                        self.ai_engine.train_regime_model(df)

                    decision = self.ai_engine.evaluate(df, symbol=symbol, timeframe=self.timeframe_str)
                    with self.data_lock:
                        self.symbol_regimes[symbol] = decision.regime

                    # Detailed Decision Log
                    if decision.signal == SignalType.HOLD:
                        logging.info(f"[{symbol}] AI: HOLD (Regime: {decision.regime}, Filter: {decision.filter_decision}, Reason: {decision.filter_reason})")
                    else:
                        logging.info(f"[{symbol}] AI Signal: {decision.signal} (Regime: {decision.regime})")

                    if decision.is_actionable:
                        max_pos = self.risk_manager.config.get('max_position_size', 0.1)
                        signal = {
                            'symbol': symbol,
                            'type': 0 if decision.signal in [SignalType.LONG, SignalType.REDUCED_LONG] else 1,
                            'volume': float(max_pos)
                        }
                        status, validated_signal = self.risk_manager.check_order(
                            signal, active_trades_count=len(self.active_trades)
                        )
                        if status in ['approved', 'modified']:
                            self.bridge.place_order(
                                symbol=validated_signal['symbol'],
                                order_type=validated_signal['type'],
                                volume=validated_signal['volume']
                            )
                except Exception as e:
                    logging.error(f"AI Strategy Error [{symbol}]: {e}")

    def start(self):
        logging.info("Trading Engine Activated.")
        self.running = True

    def stop(self):
        self.running = False
        logging.info("Trading Engine Deactivated.")

    def set_timeframe(self, tf_str):
        self.timeframe_str = tf_str
        self.mt5_timeframe = self.tf_map.get(tf_str, 16385)
        # Force re-training on new timeframe
        if self.ai_engine:
            self.ai_engine._trained = False
        logging.info(f"Engine timeframe updated to {tf_str}")

    def get_account_info(self):
        # Return cached data so API calls are instant
        return self.account_cache if self.account_cache else self.bridge.get_account_info()

    def close_all_trades(self):
        logging.info("Closing all active trades...")
        for pos in self.active_trades:
            self.bridge.close_position(pos['id'])
        return True

    def calculate_total_pnl(self):
        # Calculate NET floating profit (Profit + Commission + Swap)
        return sum(trade.get('profit', 0) + trade.get('commission', 0) + trade.get('swap', 0) for trade in self.active_trades)

    def get_active_trades(self):
        return self.active_trades

    def get_market_scanner(self):
        enriched = []
        for symbol, data in self.market_scanner.items():
            enriched.append({
                "symbol": symbol,
                "bid": data['bid'],
                "ask": data['ask'],
                "change": data.get('change', 0.0),
                "trend": data.get('trend', "neutral"),
                "regime": self.symbol_regimes.get(symbol, "analyzing...")
            })
        return enriched

    def get_equity_history(self):
        return [{"timestamp": p['time'] * 1000, "equity": p['equity']} for p in self.equity_history]

    def get_market_regime(self):
        return ""

    def generate_dummy_signal(self, symbol):
        return None
