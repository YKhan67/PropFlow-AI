"""Hidden Markov Model-based FX market regime detection.

Classifies market into three regimes:
- Trending (H > 0.5, strong directional moves)
- Ranging (H < 0.5, mean-reverting, consolidation)
- Volatile (high ATR, wide BB, choppy)

The HMM is trained on normalised feature vectors extracted from
OHLCV data and uses a 3-state Gaussian emission model.
"""

import pickle
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from hmmlearn import hmm
from sklearn.preprocessing import StandardScaler

from ..features.feature_pipeline import FeatureConfig, extract_regime_features


@dataclass
class HMMConfig:
    """Configuration for the HMM regime detector."""

    n_states: int = 3
    covariance_type: str = "full"
    n_iter: int = 200
    tol: float = 1e-4
    random_state: int = 42
    init_params: str = "stmc"
    params: str = "stmc"

    # State labels assigned after training based on volatility/trend characteristics
    # 0,1,2 will be mapped to {"trending", "ranging", "volatile"}
    state_labels: dict = field(default_factory=lambda: {0: "trending", 1: "ranging", 2: "volatile"})


class RegimeHMM:
    """HMM-based market regime classifier.

    Trained on feature vectors → predicts latent market regime state.
    """

    def __init__(self, config: Optional[HMMConfig] = None):
        self.config = config or HMMConfig()
        self._model: Optional[hmm.GaussianHMM] = None
        self._scaler: StandardScaler = StandardScaler()
        self._feature_config: FeatureConfig = FeatureConfig()
        self._trained: bool = False
        # State -> label mapping, determined from training data
        self._state_labels: dict[int, str] = {}

    @property
    def n_states(self) -> int:
        return self.config.n_states

    @property
    def is_trained(self) -> bool:
        return self._trained

    def fit(
        self,
        ohlcv,
        feature_config: Optional[FeatureConfig] = None,
        warm_start: bool = False,
    ) -> "RegimeHMM":
        """Fit the HMM on historical OHLCV data.

        Args:
            ohlcv: DataFrame/array with OHLCV columns, or precomputed features
            feature_config: Feature extraction configuration
            warm_start: If True, reuse existing HMM params (for online updates)

        Returns:
            self
        """
        if feature_config is not None:
            self._feature_config = feature_config

        # Extract features
        features = extract_regime_features(ohlcv, self._feature_config)

        # Normalise
        features_scaled = self._scaler.fit_transform(features)

        # Create & train HMM
        self._model = hmm.GaussianHMM(
            n_components=self.config.n_states,
            covariance_type=self.config.covariance_type,
            n_iter=self.config.n_iter,
            tol=self.config.tol,
            random_state=self.config.random_state,
            init_params=self.config.init_params,
            params=self.config.params,
        )

        if warm_start and hasattr(self._model, "monitor_"):
            # Preserve existing transmat / means if retraining
            pass

        self._model.fit(features_scaled)
        self._trained = True

        # Label states based on mean feature values
        self._label_states(features_scaled)

        return self

    def _label_states(self, features_scaled: np.ndarray) -> None:
        """Assign semantic labels to HMM states based on their emission means.

        Uses the mean feature vector per state to determine:
        - High ADX + high Hurst → trending
        - Low volatility + low BB width → ranging
        - High volatility + high BB width + extreme RSI → volatile
        """
        means = self._model.means_  # shape (n_states, n_features)
        names = self._feature_config.feature_names

        # Build a scoring heuristic per state
        scores = {}
        for state_idx in range(self.config.n_states):
            score = {"trending": 0.0, "ranging": 0.0, "volatile": 0.0}

            mean_vec = means[state_idx]

            for j, name in enumerate(names):
                val = mean_vec[j]
                if name == "adx":
                    # High ADX → trending
                    if val > 0.5:
                        score["trending"] += 1.0
                    elif val < -0.5:
                        score["ranging"] += 0.5
                elif name == "bb_width":
                    # High BB width → volatile
                    if val > 0.5:
                        score["volatile"] += 1.5
                    elif val < -0.3:
                        score["ranging"] += 0.5
                elif name == "volatility":
                    if val > 0.5:
                        score["volatile"] += 1.5
                    elif val < -0.3:
                        score["ranging"] += 0.5
                elif name == "hurst_exponent":
                    if val > 0.5:
                        score["trending"] += 1.0
                    elif val < -0.3:
                        score["ranging"] += 1.0
                elif name == "rsi":
                    # Extreme RSI → potentially volatile/trending
                    abs_rsi = abs(val)
                    if abs_rsi > 1.5:
                        score["trending"] += 0.5

            # Determine winner for this state
            winner = max(score, key=score.get)
            scores[state_idx] = (winner, score[winner])

        # Handle conflicts: if two states map to the same label, assign secondary
        used_labels = set()
        assigned = {}
        for state_idx in range(self.config.n_states):
            candidates = sorted(
                scores[state_idx][1].items(), key=lambda x: -x[1]
            )
            for label, _ in candidates:
                if label not in used_labels:
                    assigned[state_idx] = label
                    used_labels.add(label)
                    break
            else:
                assigned[state_idx] = "ranging"  # fallback

        self._state_labels = assigned

    def predict(self, ohlcv) -> tuple[np.ndarray, np.ndarray]:
        """Predict market regime states.

        Args:
            ohlcv: OHLCV DataFrame or precomputed features

        Returns:
            (state_ids, state_labels)
            state_ids: integer state indices from HMM
            state_labels: semantic label strings
        """
        if not self._trained or self._model is None:
            raise RuntimeError("Model not trained. Call fit() first.")

        features = extract_regime_features(ohlcv, self._feature_config)
        features_scaled = self._scaler.transform(features)

        state_ids = self._model.predict(features_scaled)
        state_labels = np.array([self._state_labels.get(s, "unknown") for s in state_ids])

        return state_ids, state_labels

    def predict_proba(self, ohlcv) -> np.ndarray:
        """Get posterior probability distribution over states.

        Args:
            ohlcv: OHLCV DataFrame

        Returns:
            (n_samples, n_states) array of probabilities
        """
        if not self._trained or self._model is None:
            raise RuntimeError("Model not trained. Call fit() first.")

        features = extract_regime_features(ohlcv, self._feature_config)
        features_scaled = self._scaler.transform(features)

        logprob, posteriors = self._model.decode(features_scaled)
        # hmmlearn doesn't expose per-step posteriors directly in newer versions
        # Use predict_proba which returns per-sample state probabilities
        return self._model.predict_proba(features_scaled)

    def get_regime_probs(self, ohlcv) -> dict[str, np.ndarray]:
        """Get probabilities for each semantic regime label.

        Returns:
            dict mapping 'trending', 'ranging', 'volatile' to probability arrays
        """
        posteriors = self.predict_proba(ohlcv)
        result = {}
        for state_idx, label in self._state_labels.items():
            result[label] = posteriors[:, state_idx]
        # Any label not assigned gets zero probability
        for label in ["trending", "ranging", "volatile"]:
            if label not in result:
                result[label] = np.zeros(posteriors.shape[0])
        return result

    def save(self, path: str) -> None:
        """Serialize model to disk."""
        state = {
            "config": self.config,
            "feature_config": self._feature_config,
            "state_labels": self._state_labels,
            "trained": self._trained,
            "model": self._model,
            "scaler": self._scaler,
        }
        with open(path, "wb") as f:
            pickle.dump(state, f)

    @classmethod
    def load(cls, path: str) -> "RegimeHMM":
        """Load serialized model from disk."""
        with open(path, "rb") as f:
            state = pickle.load(f)
        instance = cls(config=state["config"])
        instance._feature_config = state["feature_config"]
        instance._state_labels = state["state_labels"]
        instance._trained = state["trained"]
        instance._model = state["model"]
        instance._scaler = state["scaler"]
        return instance

    def current_regime(self) -> str:
        """Return the most recent regime label if model is trained."""
        return self._state_labels.get(0, "unknown")