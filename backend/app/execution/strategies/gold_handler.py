import logging
import pandas as pd
from ai.engine.gold_scalper import GoldScalperStrategy, SignalType as GoldSignalType

class GoldHandler:
    def __init__(self, risk_manager):
        self.risk_manager = risk_manager
        self.ai = GoldScalperStrategy(risk_manager.config)

    def evaluate(self, symbol, data, active_trades, bridge):
        try:
            df = pd.DataFrame.from_records(data)
            decision = self.ai.evaluate(symbol, df)

            # 1. Structural Exit Check
            active_gold_trades = [t for t in active_trades if t['symbol'] == symbol]
            if active_gold_trades and decision.signal == GoldSignalType.EXIT:
                logging.info(f"!!! [{symbol}] GOLD EXIT TRIGGERED: {decision.reason} !!!")
                for t in active_gold_trades:
                    bridge.close_position(t['id'])
                return None, decision.regime

            # 2. Entry Check
            signal = None
            if decision.signal == GoldSignalType.BUY:
                max_pos = self.risk_manager.config.get('max_position_size', 0.1)
                signal = {
                    'symbol': symbol,
                    'type': 0, # BUY
                    'volume': float(max_pos),
                    'regime': decision.regime,
                    'reason': "GOLD SCALPER"
                }
            return signal, decision.regime
        except Exception as e:
            logging.error(f"Gold Handler Error [{symbol}]: {e}")
            return None, "error"
