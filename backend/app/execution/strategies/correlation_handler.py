import logging
import pandas as pd
from ai.engine.correlation_engine import CorrelationStrategy

class CorrelationHandler:
    def __init__(self, risk_manager):
        self.risk_manager = risk_manager
        self.ai = CorrelationStrategy(risk_manager.config)

    def evaluate(self, symbols, bridge, mt5_timeframe, timeframe_str):
        try:
            # Gather data for all symbols
            all_data = {}
            for sym in symbols:
                data = bridge.get_market_data(sym, timeframe=mt5_timeframe, count=100)
                if data is not None and len(data) > 0:
                    all_data[sym] = pd.DataFrame.from_records(data)

            if not all_data:
                return [], {}

            decisions, statuses = self.ai.evaluate(all_data, timeframe=timeframe_str)

            signals = []
            for d in decisions:
                max_pos = self.risk_manager.config.get('max_position_size', 0.1)
                basket = []
                for sig in d.signals:
                    basket.append({
                        'symbol': sig['symbol'],
                        'type': sig['type'],
                        'volume': float(max_pos),
                        'reason': d.reason
                    })
                signals.append({'type': 'basket', 'trades': basket, 'pair_a': d.pair_a, 'pair_b': d.pair_b, 'reason': d.reason, 'coef': d.coefficient})

            return signals, statuses
        except Exception as e:
            logging.error(f"Correlation Handler Error: {e}")
            return [], {}
