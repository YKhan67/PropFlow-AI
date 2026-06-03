"""Currency Correlation Reversion Strategy.

Identifies divergence between highly correlated (or negatively correlated) pairs
and trades the reversion to their normal relationship.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional, Tuple
import logging

class CorrelationDecision:
    def __init__(self, signals: List[Dict], pair_a: str, pair_b: str, coefficient: float, reason: str):
        self.signals = signals # List of dicts: {'symbol': str, 'type': 0/1}
        self.pair_a = pair_a
        self.pair_b = pair_b
        self.coefficient = coefficient
        self.reason = reason
        self.is_actionable = len(signals) > 0

class CorrelationStrategy:
    def __init__(self, config: Dict):
        self.config = config
        self.lookback = 50 # bars to calculate correlation
        self.threshold = 0.80
        self.active_pairs = ["EURUSD", "GBPUSD", "USDCHF", "USDJPY", "AUDUSD", "NZDUSD", "USDCAD"]

    def evaluate(self, all_data: Dict[str, pd.DataFrame]) -> Tuple[List[CorrelationDecision], Dict[str, str]]:
        """Analyzes all pair combinations for correlation divergence.

        Returns:
            (decisions, pair_statuses)
        """
        decisions = []
        statuses = {p: "Twin Move" for p in all_data.keys()} # Default state
        pairs = list(all_data.keys())

        for i in range(len(pairs)):
            for j in range(i + 1, len(pairs)):
                pair_a = pairs[i]
                pair_b = pairs[j]

                if pair_a not in self.active_pairs or pair_b not in self.active_pairs:
                    continue

                df_a = all_data[pair_a]
                df_b = all_data[pair_b]

                if len(df_a) < self.lookback or len(df_b) < self.lookback:
                    continue

                # Calculate Pearson Correlation
                series_a = df_a['close'].values[-self.lookback:]
                series_b = df_b['close'].values[-self.lookback:]
                corr = np.corrcoef(series_a, series_b)[0, 1]

                decision = self._check_divergence(pair_a, pair_b, series_a, series_b, corr)
                if decision:
                    decisions.append(decision)
                    # Mark leading/lagging pairs
                    if "lagging" in decision.reason.lower():
                        if decision.signals[0]['symbol'] == pair_a:
                            statuses[pair_a] = "Leading"
                            statuses[pair_b] = "Lagging"
                        else:
                            statuses[pair_a] = "Lagging"
                            statuses[pair_b] = "Leading"

        return decisions, statuses

    def _check_divergence(self, p1: str, p2: str, s1: np.ndarray, s2: np.ndarray, corr: float) -> Optional[CorrelationDecision]:
        # 1. Normalize series to percentage returns for comparison
        ret1 = (s1[-1] / s1[-5] - 1) * 100 # 5-bar return
        ret2 = (s2[-1] / s2[-5] - 1) * 100

        diff = abs(ret1 - ret2)

        # Positive Correlation Reversion (+0.80)
        if corr > self.threshold:
            if diff > 0.2: # Threshold for 'Strong Move' vs 'Lagging'
                if ret1 > ret2: # P1 leads UP, P2 lags
                    return CorrelationDecision(
                        signals=[
                            {'symbol': p1, 'type': 0}, # BUY Leading (Follow trend)
                            {'symbol': p2, 'type': 0}  # BUY Lagging (Catch up)
                        ],
                        pair_a=p1, pair_b=p2, coefficient=corr,
                        reason=f"Pos-Corr Reversion: {p2} lagging {p1}"
                    )
                elif ret1 < ret2: # P1 leads DOWN, P2 lags
                    return CorrelationDecision(
                        signals=[
                            {'symbol': p1, 'type': 1}, # SELL Leading
                            {'symbol': p2, 'type': 1}  # SELL Lagging
                        ],
                        pair_a=p1, pair_b=p2, coefficient=corr,
                        reason=f"Pos-Corr Reversion: {p1} leading {p2} down"
                    )

        # Negative Correlation Reversion (-0.80)
        elif corr < -self.threshold:
            # For negative, we expect (ret1 + ret2) ≈ 0. If sum is large, they are moving together (divergence)
            net_move = ret1 + ret2
            if abs(net_move) > 0.2:
                if ret1 > 0 and ret2 > -0.1: # P1 up, P2 failed to fall
                    return CorrelationDecision(
                        signals=[
                            {'symbol': p1, 'type': 0}, # BUY P1
                            {'symbol': p2, 'type': 1}  # SELL P2 (Revert to inverse)
                        ],
                        pair_a=p1, pair_b=p2, coefficient=corr,
                        reason=f"Neg-Corr Reversion: {p2} failed to invert {p1}"
                    )
                elif ret1 < 0 and ret2 < 0.1: # P1 down, P2 failed to rise
                    return CorrelationDecision(
                        signals=[
                            {'symbol': p1, 'type': 1}, # SELL P1
                            {'symbol': p2, 'type': 0}  # BUY P2 (Revert to inverse)
                        ],
                        pair_a=p1, pair_b=p2, coefficient=corr,
                        reason=f"Neg-Corr Reversion: {p1} down, {p2} lagging inverse"
                    )

        return None
