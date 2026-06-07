import logging
import pandas as pd
from ai.engine.quant_engine import FXQuantEngine

class QuantHandler:
    def __init__(self, risk_manager):
        self.risk_manager = risk_manager
        self.ai = FXQuantEngine(risk_manager.config)

    def evaluate(self, symbol, data, market_scanner):
        try:
            df = pd.DataFrame.from_records(data)
            ticker = market_scanner.get(symbol)
            current_price = ticker['last'] if ticker else df['close'].iloc[-1]

            decision = self.ai.evaluate(symbol, df, market_scanner, current_price)

            signal = None
            if decision.trade_status == "executed":
                order_type = 0 if decision.direction == "long" else 1
                signal = {
                    'symbol': symbol,
                    'type': order_type,
                    'volume': decision.position_size,
                    'sl': decision.stop_loss,
                    'tp': decision.take_profit,
                    'regime': decision.market_regime,
                    'reason': decision.direction.upper()
                }
            return signal, decision.market_regime
        except Exception as e:
            logging.error(f"Quant Handler Error [{symbol}]: {e}")
            return None, "error"
