import logging
import pandas as pd
from ai.engine.hybrid_engine import HybridDecisionEngine, SignalType as HybridSignalType

class HMMHandler:
    def __init__(self, risk_manager):
        self.risk_manager = risk_manager
        self.ai = HybridDecisionEngine()

        # Initial sync from risk manager
        self.ai.signal_gate.dd_config.min_time_between_trades_seconds = self.risk_manager.config.get('min_time_between_trades', 300)
        self.ai.signal_gate.dd_config.daily_drawdown_limit_pct = self.risk_manager.config.get('max_daily_drawdown', 0.05) * 100
        self.ai.signal_gate.dd_config.total_drawdown_limit_pct = self.risk_manager.config.get('max_total_drawdown', 0.10) * 100

    def evaluate(self, symbol, data, timeframe_str):
        try:
            df = pd.DataFrame.from_records(data)
            if not self.ai.is_trained(symbol):
                logging.info(f"[{symbol}] Initializing HMM model...")
                self.ai.train_regime_model(symbol, df)

            decision = self.ai.evaluate(df, symbol=symbol, timeframe=timeframe_str)

            signal = None
            if decision.is_actionable:
                max_pos = self.risk_manager.config.get('max_position_size', 0.1)
                signal = {
                    'symbol': symbol,
                    'type': 0 if decision.signal in [HybridSignalType.LONG, HybridSignalType.REDUCED_LONG] else 1,
                    'volume': float(max_pos),
                    'regime': decision.regime,
                    'reason': decision.signal.value.upper()
                }
            return signal, decision.regime
        except Exception as e:
            logging.error(f"HMM Handler Error [{symbol}]: {e}")
            return None, "error"
