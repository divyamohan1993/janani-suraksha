"""Position-prediction MLP following the learned index paradigm (Kraska et al., 2018).

Reference: Kraska T et al., "The Case for Learned Index Structures",
SIGMOD 2018:489-504, DOI:10.1145/3183713.3196909 (arXiv:1712.01208, 2017).

A 2-layer MLP (5->64->32->1) approximates the CDF of sorted hemoglobin
trajectories, predicting the position of the best-matching trajectory
from raw continuous features. Local search over +/-max_error positions
refines the match. Total query time: O(1) bounded.

Key advantage over hash-based discretized lookup:
- Accepts continuous inputs directly (no discretization collisions)
- Generalizes to unseen input combinations via learned function
- Model size: ~2,500 parameters (~20 KB as JSON)

No runtime dependencies beyond Python stdlib (pure-Python matrix ops).
numpy is used only at training time (precomputation step).
"""

import json
import math
from typing import Optional


class LearnedIndex:
    """2-layer MLP learned index for O(1) trajectory position prediction.

    Architecture: Linear(5,64) → ReLU → Linear(64,32) → ReLU → Linear(32,1) → Sigmoid × N

    Trained on (raw_features → normalized_position) pairs from sorted trajectory array.
    At query time: MLP predicts approximate position → local search ±max_error → exact match.
    """

    def __init__(self):
        # MLP weights: list-of-lists for pure-Python matrix multiply
        self._w1: list[list[float]] = []  # 64 x 5
        self._b1: list[float] = []        # 64
        self._w2: list[list[float]] = []  # 32 x 64
        self._b2: list[float] = []        # 32
        self._w3: list[list[float]] = []  # 1 x 32
        self._b3: list[float] = []        # 1
        self._n_trajectories: int = 0
        self._max_error: int = 5          # bounded local search window
        self._input_min: list[float] = []  # feature normalization
        self._input_max: list[float] = []
        self._loaded = False

    def load(self, path: str) -> None:
        """Load trained MLP weights from JSON file."""
        with open(path) as f:
            data = json.load(f)
        self._w1 = data["w1"]
        self._b1 = data["b1"]
        self._w2 = data["w2"]
        self._b2 = data["b2"]
        self._w3 = data["w3"]
        self._b3 = data["b3"]
        self._n_trajectories = data["n_trajectories"]
        self._max_error = data.get("max_error", 5)
        self._input_min = data["input_min"]
        self._input_max = data["input_max"]
        self._loaded = True

    def _normalize_input(self, features: list[float]) -> list[float]:
        """Min-max normalize input features to [0, 1]."""
        normalized = []
        for i, val in enumerate(features):
            range_val = self._input_max[i] - self._input_min[i]
            if range_val == 0:
                normalized.append(0.0)
            else:
                normalized.append((val - self._input_min[i]) / range_val)
        return normalized

    @staticmethod
    def _relu(x: float) -> float:
        return max(0.0, x)

    @staticmethod
    def _sigmoid(x: float) -> float:
        if x >= 0:
            return 1.0 / (1.0 + math.exp(-x))
        else:
            exp_x = math.exp(x)
            return exp_x / (1.0 + exp_x)

    def _forward(self, features: list[float]) -> float:
        """Pure-Python MLP forward pass: 5 → 64 → 32 → 1.

        Returns predicted position as float in [0, n_trajectories].
        """
        x = self._normalize_input(features)

        # Layer 1: Linear(5, 64) + ReLU
        h1 = []
        for i in range(len(self._w1)):
            val = self._b1[i]
            for j in range(len(x)):
                val += self._w1[i][j] * x[j]
            h1.append(self._relu(val))

        # Layer 2: Linear(64, 32) + ReLU
        h2 = []
        for i in range(len(self._w2)):
            val = self._b2[i]
            for j in range(len(h1)):
                val += self._w2[i][j] * h1[j]
            h2.append(self._relu(val))

        # Layer 3: Linear(32, 1) + Sigmoid
        val = self._b3[0]
        for j in range(len(h2)):
            val += self._w3[0][j] * h2[j]

        # Sigmoid → [0, 1] → scale to [0, N]
        return self._sigmoid(val) * self._n_trajectories

    def predict_position(self, initial_hb: float, gest_weeks: int,
                         ifa_compliance: float, dietary_score: float,
                         prev_anemia: bool) -> int:
        """Predict trajectory position from raw continuous features.

        Returns the predicted index in the sorted trajectory array.
        The caller should search ±max_error positions for the best match.
        """
        features = [
            initial_hb,
            float(gest_weeks),
            ifa_compliance,
            dietary_score,
            1.0 if prev_anemia else 0.0,
        ]
        raw_pos = self._forward(features)
        # Clamp to valid range
        return max(0, min(int(round(raw_pos)), self._n_trajectories - 1))

    def search_window(self, predicted_pos: int) -> tuple[int, int]:
        """Return the bounded search window [lo, hi] around predicted position."""
        lo = max(0, predicted_pos - self._max_error)
        hi = min(self._n_trajectories - 1, predicted_pos + self._max_error)
        return lo, hi

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def max_error(self) -> int:
        return self._max_error

    @property
    def n_parameters(self) -> int:
        """Total number of MLP parameters."""
        if not self._loaded:
            return 0
        return (
            len(self._w1) * len(self._w1[0]) + len(self._b1) +
            len(self._w2) * len(self._w2[0]) + len(self._b2) +
            len(self._w3) * len(self._w3[0]) + len(self._b3)
        )
