import logging
import os
import time

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    logging.warning("MetaTrader5 package not found. Using Mock MT5.")

class MT5Bridge:
    def __init__(self, login=None, password=None, server=None):
        self.login = login
        self.password = password
        self.server = server
        self.connected = False

    def initialize(self):
        if MT5_AVAILABLE:
            if not mt5.initialize(login=self.login, password=self.password, server=self.server):
                logging.error(f"Failed to initialize MT5: {mt5.last_error()}")
                return False
            self.connected = True
            return True
        else:
            logging.info("Mock MT5 initialized.")
            self.connected = True
            return True

    def get_market_data(self, symbol, timeframe, count=100):
        if MT5_AVAILABLE:
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
            return rates
        else:
            # Mock data return
            import numpy as np
            import pandas as pd
            dates = pd.date_range(end=pd.Timestamp.now(), periods=count, freq='h')
            data = {
                'time': dates.view(np.int64) // 10**9,
                'open': np.random.uniform(1.0, 1.1, count),
                'high': np.random.uniform(1.1, 1.2, count),
                'low': np.random.uniform(0.9, 1.0, count),
                'close': np.random.uniform(1.0, 1.1, count),
                'tick_volume': np.random.randint(100, 1000, count),
                'spread': [2] * count,
                'real_volume': [0] * count
            }
            return pd.DataFrame(data).to_records(index=False)

    def place_order(self, symbol, order_type, volume, price=None, sl=None, tp=None):
        if MT5_AVAILABLE:
            # Placeholder for actual MT5 order placement
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "magic": 123456,
                "comment": "PropFlow AI Trade",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            if price: request["price"] = price
            if sl: request["sl"] = sl
            if tp: request["tp"] = tp
            
            result = mt5.order_send(request)
            return result
        else:
            logging.info(f"Mock Order Placed: {symbol}, {order_type}, vol={volume}")
            return {"retcode": 10009, "comment": "Request executed", "order": 12345}

    def get_symbol_info(self, symbol):
        if MT5_AVAILABLE:
            info = mt5.symbol_info_tick(symbol)
            if info:
                return {
                    "symbol": symbol,
                    "bid": info.bid,
                    "ask": info.ask,
                    "last": info.last,
                    "time": info.time
                }
            return None
        else:
            # Mock symbol info
            import random
            bid = 1.05 + random.uniform(-0.01, 0.01)
            return {
                "symbol": symbol,
                "bid": bid,
                "ask": bid + 0.0002,
                "last": bid + 0.0001,
                "time": int(time.time())
            }

    def shutdown(self):
        if MT5_AVAILABLE:
            mt5.shutdown()
        self.connected = False
