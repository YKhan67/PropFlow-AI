import logging
import time
from app.broker.mt5_broker import MT5Bridge
from app.services.risk_engine import RiskManager

class ExecutionEngine:
    def __init__(self, symbols, risk_config):
        self.symbols = symbols
        self.bridge = MT5Bridge()
        self.risk_manager = RiskManager(risk_config)
        self.running = False
        self.active_trades = []
        self.market_scanner = {}
        self.equity_history = []

    def start(self):
        logging.info("Starting Execution Engine...")
        if not self.bridge.initialize():
            logging.error("Failed to initialize MT5 Bridge.")
            return

        self.running = True
        self.run_loop()

    def stop(self):
        self.running = False
        self.bridge.shutdown()
        logging.info("Execution Engine stopped.")

    def run_loop(self):
        while self.running:
            # Update Equity and Risk Manager
            current_pnl = self.calculate_total_pnl()
            new_equity = self.risk_manager.starting_balance + current_pnl
            self.risk_manager.update_equity(new_equity)
            self.equity_history.append({
                "time": time.time(),
                "equity": new_equity
            })
            if len(self.equity_history) > 100:
                self.equity_history.pop(0)

            for symbol in self.symbols:
                # 1. Update Market Scanner Data
                ticker = self.bridge.get_symbol_info(symbol)
                if ticker:
                    self.market_scanner[symbol] = ticker

                # 2. Fetch Market Data for Strategy
                data = self.bridge.get_market_data(symbol, 1) # 1H timeframe for example
                if data is not None:
                    # 3. Strategy Logic (to be implemented by ai-engineer or others)
                    signal = self.generate_dummy_signal(symbol)
                    
                    if signal:
                        # 4. Risk Check
                        status, validated_signal = self.risk_manager.check_order(signal)
                        if status in ['approved', 'modified']:
                            # 5. Execute
                            result = self.bridge.place_order(
                                symbol=validated_signal['symbol'],
                                order_type=validated_signal['type'],
                                volume=validated_signal['volume']
                            )
                            logging.info(f"Order Execution Result: {result}")
                            if result.get('retcode') == 10009:
                                self.active_trades.append({
                                    "symbol": validated_signal['symbol'],
                                    "type": "BUY" if validated_signal['type'] == 0 else "SELL",
                                    "volume": validated_signal['volume'],
                                    "open_price": ticker['last'] if ticker else 1.05,
                                    "time": time.time()
                                })
                        else:
                            logging.warning(f"Order blocked by Risk Manager: {signal}")

            time.sleep(5) # Run every 5 seconds

    def calculate_total_pnl(self):
        total_pnl = 0
        for trade in self.active_trades:
            ticker = self.market_scanner.get(trade['symbol'])
            if ticker:
                current_price = ticker['last']
                if trade['type'] == "BUY":
                    # Simple PnL calculation (price diff * volume * contract size multiplier)
                    # For EURUSD, 1 lot is 100,000 units. 1 pip is 0.0001.
                    # Simplified mock calculation:
                    total_pnl += (current_price - trade['open_price']) * trade['volume'] * 100000
                else:
                    total_pnl += (trade['open_price'] - current_price) * trade['volume'] * 100000
        return total_pnl

    def get_active_trades(self):
        # Update current price and PnL for each active trade before returning
        trades_with_pnl = []
        for trade in self.active_trades:
            ticker = self.market_scanner.get(trade['symbol'])
            current_price = ticker['last'] if ticker else trade['open_price']
            pnl = 0
            if ticker:
                if trade['type'] == "BUY":
                    pnl = (current_price - trade['open_price']) * trade['volume'] * 100000
                else:
                    pnl = (trade['open_price'] - current_price) * trade['volume'] * 100000
            
            trade_copy = trade.copy()
            trade_copy['current_price'] = current_price
            trade_copy['pnl'] = pnl
            trades_with_pnl.append(trade_copy)
        return trades_with_pnl

    def get_market_scanner(self):
        return list(self.market_scanner.values())

    def get_equity_history(self):
        return self.equity_history

    def generate_dummy_signal(self, symbol):
        # Placeholder signal generation
        import random
        if random.random() > 0.95:
            return {
                'symbol': symbol,
                'type': 0, # Buy
                'volume': 0.1
            }
        return None
