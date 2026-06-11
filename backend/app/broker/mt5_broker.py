import logging
import os
import time
import datetime
import threading

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
        self.last_error = ""

    def initialize(self):
        if MT5_AVAILABLE:
            logging.info("Attempting to initialize MT5...")
            # Ensure types are correct for MT5 API
            login = int(self.login) if self.login and str(self.login).isdigit() else None
            password = str(self.password) if self.password else None
            server = str(self.server) if self.server else None

            if login:
                logging.info(f"Using provided credentials for account {login}")
                success = mt5.initialize(login=login, password=password, server=server)
            else:
                logging.info("Using default/cached MT5 credentials")
                success = mt5.initialize() # Try last used account if no credentials

            if not success:
                err_code, err_msg = mt5.last_error()
                self.last_error = f"Init failed: {err_msg} ({err_code})"
                logging.error(f"Failed to initialize MT5: {self.last_error}")
                self.connected = False
                return False

            logging.info("MT5 base initialization successful. Fetching account info...")
            account_info = mt5.account_info()
            if account_info:
                logging.info(f"Connected to MT5! Account: {account_info.login}, Name: {account_info.name}")
                self.connected = True
                self.last_error = ""
                return True
            else:
                err_code, err_msg = mt5.last_error()
                self.last_error = f"Login failed: {err_msg} ({err_code})"
                logging.error(f"MT5 Initialized but no account logged in. {self.last_error}")
                self.connected = False
                return False
        else:
            self.last_error = "MetaTrader5 package not found"
            logging.info("Mock MT5 initialized.")
            self.connected = True
            return True

    def get_account_info(self):
        if MT5_AVAILABLE:
            if not self.connected:
                self.initialize()

            acc = mt5.account_info()
            if acc:
                return {
                    "login": acc.login,
                    "name": acc.name,
                    "server": acc.server,
                    "balance": acc.balance,
                    "equity": acc.equity,
                    "company": acc.company,
                    "connected": True,
                    "error": ""
                }
            else:
                err_code, err_msg = mt5.last_error()
                return {
                    "login": 0,
                    "name": "Disconnected",
                    "server": "",
                    "balance": 0,
                    "equity": 0,
                    "company": "",
                    "connected": False,
                    "error": f"{err_msg} ({err_code})"
                }

        return {
            "login": 1234567,
            "name": "Mock Trader",
            "server": "Mock-Server",
            "balance": 100000.0,
            "equity": 100000.0,
            "company": "PropFlow AI Mock Broker",
            "connected": True,
            "error": "Using Mock Mode"
        }

    def get_market_data(self, symbol, timeframe=None, count=250):
        if MT5_AVAILABLE:
            # Default to H1 if no timeframe provided
            tf = timeframe if timeframe else mt5.TIMEFRAME_H1
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
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

    def get_market_data_range(self, symbol, timeframe, date_from, date_to):
        """Fetches historical data for a specific range."""
        if MT5_AVAILABLE:
            if not self.connected:
                self.initialize()

            rates = mt5.copy_rates_range(symbol, timeframe, date_from, date_to)
            return rates
        else:
            # Mock data for range
            import numpy as np
            import pandas as pd
            # Calculate number of bars based on range and timeframe (roughly)
            # This is a simplification for mock mode
            count = 1000
            dates = pd.date_range(start=date_from, end=date_to, periods=count)
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
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                logging.error(f"Failed to get tick info for {symbol}")
                return {"retcode": -1, "comment": "No tick info"}

            if price is None:
                price = tick.ask if order_type == 0 else tick.bid

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(volume),
                "type": mt5.ORDER_TYPE_BUY if order_type == 0 else mt5.ORDER_TYPE_SELL,
                "price": float(price),
                "magic": 123456,
                "comment": "PropFlow AI Trade",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            if sl: request["sl"] = float(sl)
            if tp: request["tp"] = float(tp)

            logging.info(f"Sending order to MT5: {symbol} {'BUY' if order_type == 0 else 'SELL'} {volume} @ {price}")
            result = mt5.order_send(request)

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logging.error(f"Order failed: {result.comment} (code: {result.retcode})")
            else:
                logging.info(f"Order executed successfully! Ticket: {result.order}")

            return {
                "retcode": result.retcode,
                "comment": result.comment,
                "order": result.order,
                "deal": result.deal,
                "price": result.price
            }
        else:
            logging.info(f"Mock Order Placed: {symbol}, {order_type}, vol={volume}")
            return {"retcode": 10009, "comment": "Request executed", "order": 12345}

    def close_position(self, ticket, volume=None):
        if MT5_AVAILABLE:
            positions = mt5.positions_get(ticket=int(ticket))
            if positions is None or len(positions) == 0:
                logging.error(f"Failed to find position {ticket} to close")
                return False

            pos = positions[0]
            symbol = pos.symbol
            # Use provided volume or full position volume
            close_volume = float(volume) if volume is not None else float(pos.volume)

            # Ensure we don't try to close more than exists
            close_volume = min(close_volume, float(pos.volume))

            order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY

            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                logging.error(f"Failed to get tick info for {symbol}")
                return False

            price = tick.bid if order_type == mt5.ORDER_TYPE_SELL else tick.ask

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": close_volume,
                "type": order_type,
                "position": int(ticket),
                "price": float(price),
                "magic": 123456,
                "comment": "PropFlow Partial Close" if volume else "PropFlow Close All",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logging.error(f"Failed to close position {ticket}: {result.comment}")
                return False

            logging.info(f"Closed {close_volume} of position {ticket} successfully")
            return True
        return True

    def get_symbol_info(self, symbol):
        if MT5_AVAILABLE:
            try:
                tick = mt5.symbol_info_tick(symbol)
                info = mt5.symbol_info(symbol)

                if tick is not None and info is not None:
                    # Calculate daily change if possible
                    daily_change = 0.0
                    p_change = getattr(info, 'price_change', 0.0)
                    p_open = getattr(info, 'price_open', 0.0)

                    if p_change:
                        daily_change = float(p_change)
                    elif p_open and p_open > 0:
                        daily_change = ((float(tick.bid) - float(p_open)) / float(p_open)) * 100

                    return {
                        "symbol": symbol,
                        "bid": float(tick.bid),
                        "ask": float(tick.ask),
                        "last": float(tick.last),
                        "time": int(tick.time),
                        "change": daily_change,
                        "trend": "up" if daily_change >= 0 else "down"
                    }
            except Exception as e:
                logging.error(f"Error fetching symbol info for {symbol}: {e}")
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
                "time": int(time.time()),
                "change": 0.05,
                "trend": "up"
            }

    def get_open_positions(self):
        if MT5_AVAILABLE:
            if not self.connected:
                self.initialize()

            positions = mt5.positions_get()
            if positions is None:
                return []

            result = []
            for p in positions:
                result.append({
                    "id": str(p.ticket),
                    "symbol": p.symbol,
                    "type": "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
                    "volume": float(p.volume),
                    "open_price": float(p.price_open),
                    "current_price": float(p.price_current),
                    "time": int(p.time),
                    "profit": float(p.profit),
                    "commission": float(getattr(p, 'commission', 0.0)),
                    "swap": float(getattr(p, 'swap', 0.0)),
                    "open_time": datetime.datetime.fromtimestamp(p.time).isoformat(),
                    "entry": p.type
                })
            return result
        return []

    def get_trade_history(self, days=30):
        if MT5_AVAILABLE:
            if not self.connected:
                self.initialize()

            from_date = datetime.datetime(2024, 1, 1)
            to_date = datetime.datetime.now() + datetime.timedelta(days=1)

            history = mt5.history_deals_get(from_date, to_date)

            if history is None:
                return []

            result = []
            for d in history:
                if d.type not in [0, 1]:
                    continue

                result.append({
                    "ticket": d.ticket,
                    "order": d.order,
                    "time": d.time,
                    "symbol": d.symbol,
                    "type": "BUY" if d.type == 0 else "SELL",
                    "volume": float(d.volume),
                    "profit": float(d.profit),
                    "commission": float(d.commission),
                    "swap": float(d.swap),
                    "comment": d.comment,
                    "entry": d.entry
                })
            return result
        return []

    def shutdown(self):
        if MT5_AVAILABLE and self.connected:
            logging.info("Closing MT5 connection (non-blocking)...")
            try:
                # mt5.shutdown can hang if terminal is not responsive.
                # We run it in a daemon thread and don't wait for it to finish.
                shutdown_thread = threading.Thread(target=mt5.shutdown, daemon=True)
                shutdown_thread.start()
            except Exception as e:
                logging.error(f"Error during MT5 shutdown: {e}")
        self.connected = False
