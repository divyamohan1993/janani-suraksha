"""Trains a position-prediction MLP on the sorted trajectory array.

This follows the learned index paradigm (Kraska et al., arXiv:1712.01208, 2017)
where a model approximates the CDF of sorted data to predict record positions.

Architecture: Linear(5, 64) → ReLU → Linear(64, 32) → ReLU → Linear(32, 1) → Sigmoid

Training data: (raw_features, normalized_position) pairs from the sorted trajectory array.
Loss: Mean Squared Error on normalized positions.
Optimizer: Adam (Kingma & Ba, 2014).

Requires numpy (build-time dependency only — not needed at runtime).

Usage:
    python -m app.precompute.train_learned_index
"""

import json
import math
import os
import sys

import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

TRAJECTORIES_PATH = os.path.join(PROJECT_ROOT, "data", "hb_trajectories.json")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "data", "learned_index_weights.json")

# Training hyperparameters
HIDDEN1 = 64
HIDDEN2 = 32
LEARNING_RATE = 0.001
EPOCHS = 500
BATCH_SIZE = 256
SEED = 42


def sigmoid(x: np.ndarray) -> np.ndarray:
    return np.where(x >= 0, 1 / (1 + np.exp(-x)), np.exp(x) / (1 + np.exp(x)))


def sigmoid_grad(s: np.ndarray) -> np.ndarray:
    return s * (1 - s)


def relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(0, x)


def relu_grad(x: np.ndarray) -> np.ndarray:
    return (x > 0).astype(float)


class AdamOptimizer:
    """Adam optimizer (Kingma & Ba, 2014)."""

    def __init__(self, lr: float = 0.001, beta1: float = 0.9,
                 beta2: float = 0.999, eps: float = 1e-8):
        self.lr = lr
        self.beta1 = beta1
        self.beta2 = beta2
        self.eps = eps
        self.t = 0
        self.m: dict[str, np.ndarray] = {}
        self.v: dict[str, np.ndarray] = {}

    def update(self, name: str, param: np.ndarray, grad: np.ndarray) -> np.ndarray:
        self.t += 1
        if name not in self.m:
            self.m[name] = np.zeros_like(param)
            self.v[name] = np.zeros_like(param)
        self.m[name] = self.beta1 * self.m[name] + (1 - self.beta1) * grad
        self.v[name] = self.beta2 * self.v[name] + (1 - self.beta2) * grad ** 2
        m_hat = self.m[name] / (1 - self.beta1 ** self.t)
        v_hat = self.v[name] / (1 - self.beta2 ** self.t)
        return param - self.lr * m_hat / (np.sqrt(v_hat) + self.eps)


def build_training_data(trajectories_path: str) -> tuple[np.ndarray, np.ndarray, list[float], list[float]]:
    """Build (features, normalized_positions) training pairs from sorted trajectories.

    The trajectory file contains profiles sorted by predicted_delivery_hb.
    The index maps discretized keys to positions. We reconstruct the raw features
    from the key and map to the sorted position.
    """
    with open(trajectories_path) as f:
        data = json.load(f)

    index = data["index"]
    n = len(data["trajectories"])

    features_list = []
    positions_list = []

    # Feature grid definitions (must match generate_hb_trajectories.py)
    hb_levels = [3.0 + i * 1.0 for i in range(17)]
    gest_weeks = [i * 4 for i in range(11)]
    ifa_compliance = [0.0, 0.25, 0.5, 0.75, 1.0]
    dietary_scores = [0.0, 0.33, 0.67, 1.0]
    prev_anemia = [False, True]

    for hb in hb_levels:
        for gw in gest_weeks:
            for ifa in ifa_compliance:
                for diet in dietary_scores:
                    for anemia in prev_anemia:
                        # Reconstruct discretized key
                        hb_bucket = min(int((hb - 3.0) / 1.0), 16)
                        hb_bucket = max(0, hb_bucket)
                        gest_bucket = min(gw // 4, 10)
                        ifa_bucket = min(int(ifa * 4), 4)
                        diet_bucket = min(int(diet * 3), 3)
                        anemia_flag = 1 if anemia else 0
                        key = f"{hb_bucket}:{gest_bucket}:{ifa_bucket}:{diet_bucket}:{anemia_flag}"

                        if key in index:
                            pos = index[key]
                            features_list.append([
                                hb, float(gw), ifa, diet,
                                1.0 if anemia else 0.0
                            ])
                            positions_list.append(pos / n)  # Normalize to [0, 1]

    X = np.array(features_list, dtype=np.float64)
    y = np.array(positions_list, dtype=np.float64).reshape(-1, 1)

    # Compute normalization params
    input_min = X.min(axis=0).tolist()
    input_max = X.max(axis=0).tolist()

    # Normalize features to [0, 1]
    ranges = X.max(axis=0) - X.min(axis=0)
    ranges[ranges == 0] = 1.0
    X = (X - X.min(axis=0)) / ranges

    return X, y, input_min, input_max


def train(X: np.ndarray, y: np.ndarray, epochs: int = EPOCHS) -> dict:
    """Train 2-layer MLP with Adam optimizer."""
    np.random.seed(SEED)
    n_samples, n_features = X.shape

    # Xavier initialization
    w1 = np.random.randn(HIDDEN1, n_features) * math.sqrt(2.0 / n_features)
    b1 = np.zeros(HIDDEN1)
    w2 = np.random.randn(HIDDEN2, HIDDEN1) * math.sqrt(2.0 / HIDDEN1)
    b2 = np.zeros(HIDDEN2)
    w3 = np.random.randn(1, HIDDEN2) * math.sqrt(2.0 / HIDDEN2)
    b3 = np.zeros(1)

    optimizer = AdamOptimizer(lr=LEARNING_RATE)

    best_loss = float("inf")
    best_weights = None

    for epoch in range(epochs):
        # Shuffle
        perm = np.random.permutation(n_samples)
        X_shuf = X[perm]
        y_shuf = y[perm]

        epoch_loss = 0.0
        n_batches = 0

        for i in range(0, n_samples, BATCH_SIZE):
            X_batch = X_shuf[i:i + BATCH_SIZE]
            y_batch = y_shuf[i:i + BATCH_SIZE]
            batch_n = X_batch.shape[0]

            # Forward pass
            z1 = X_batch @ w1.T + b1          # (batch, 64)
            h1 = relu(z1)                      # (batch, 64)
            z2 = h1 @ w2.T + b2               # (batch, 32)
            h2 = relu(z2)                      # (batch, 32)
            z3 = h2 @ w3.T + b3               # (batch, 1)
            out = sigmoid(z3)                  # (batch, 1)

            # MSE loss
            diff = out - y_batch
            loss = np.mean(diff ** 2)
            epoch_loss += loss
            n_batches += 1

            # Backward pass
            d_out = 2.0 * diff / batch_n       # (batch, 1)
            d_z3 = d_out * sigmoid_grad(out)    # (batch, 1)

            d_w3 = d_z3.T @ h2                 # (1, 32)
            d_b3 = d_z3.sum(axis=0)             # (1,)

            d_h2 = d_z3 @ w3                   # (batch, 32)
            d_z2 = d_h2 * relu_grad(z2)         # (batch, 32)

            d_w2 = d_z2.T @ h1                 # (32, 64)
            d_b2 = d_z2.sum(axis=0)             # (32,)

            d_h1 = d_z2 @ w2                   # (batch, 64)
            d_z1 = d_h1 * relu_grad(z1)         # (batch, 64)

            d_w1 = d_z1.T @ X_batch            # (64, 5)
            d_b1 = d_z1.sum(axis=0)             # (64,)

            # Adam updates
            w1 = optimizer.update("w1", w1, d_w1)
            b1 = optimizer.update("b1", b1, d_b1)
            w2 = optimizer.update("w2", w2, d_w2)
            b2 = optimizer.update("b2", b2, d_b2)
            w3 = optimizer.update("w3", w3, d_w3)
            b3 = optimizer.update("b3", b3, d_b3)

        avg_loss = epoch_loss / n_batches

        if avg_loss < best_loss:
            best_loss = avg_loss
            best_weights = {
                "w1": w1.copy(), "b1": b1.copy(),
                "w2": w2.copy(), "b2": b2.copy(),
                "w3": w3.copy(), "b3": b3.copy(),
            }

        if (epoch + 1) % 50 == 0 or epoch == 0:
            print(f"  Epoch {epoch + 1:4d}/{epochs}  Loss: {avg_loss:.6f}")

    return best_weights


def evaluate(weights: dict, X: np.ndarray, y: np.ndarray, n_trajectories: int) -> dict:
    """Evaluate trained model: compute max error and position accuracy."""
    w1, b1 = weights["w1"], weights["b1"]
    w2, b2 = weights["w2"], weights["b2"]
    w3, b3 = weights["w3"], weights["b3"]

    # Forward pass
    h1 = relu(X @ w1.T + b1)
    h2 = relu(h1 @ w2.T + b2)
    out = sigmoid(h2 @ w3.T + b3)

    # Convert to positions
    pred_positions = (out * n_trajectories).flatten()
    true_positions = (y * n_trajectories).flatten()

    errors = np.abs(pred_positions - true_positions)
    max_error = int(np.ceil(np.max(errors)))
    mean_error = float(np.mean(errors))
    p99_error = float(np.percentile(errors, 99))
    within_5 = float(np.mean(errors <= 5) * 100)
    within_10 = float(np.mean(errors <= 10) * 100)

    return {
        "max_error": max_error,
        "mean_error": round(mean_error, 2),
        "p99_error": round(p99_error, 2),
        "within_5_pct": round(within_5, 1),
        "within_10_pct": round(within_10, 1),
    }


def main() -> None:
    print("=== Training Learned Index for Hemoglobin Trajectories ===")
    print(f"Architecture: Linear(5,{HIDDEN1}) → ReLU → Linear({HIDDEN1},{HIDDEN2}) → ReLU → Linear({HIDDEN2},1) → Sigmoid")
    print(f"Optimizer: Adam (lr={LEARNING_RATE})")
    print(f"Epochs: {EPOCHS}, Batch size: {BATCH_SIZE}")
    print()

    # Build training data
    print("Loading trajectories and building training data...")
    X, y, input_min, input_max = build_training_data(TRAJECTORIES_PATH)
    n_samples = X.shape[0]
    print(f"Training samples: {n_samples}")
    print(f"Feature ranges: {input_min} to {input_max}")
    print()

    # Load trajectory count
    with open(TRAJECTORIES_PATH) as f:
        n_trajectories = len(json.load(f)["trajectories"])
    print(f"Trajectory count: {n_trajectories}")
    print()

    # Train
    print("Training...")
    weights = train(X, y, EPOCHS)
    print()

    # Evaluate
    print("Evaluating...")
    metrics = evaluate(weights, X, y, n_trajectories)
    print(f"  Max position error:  {metrics['max_error']}")
    print(f"  Mean position error: {metrics['mean_error']}")
    print(f"  P99 position error:  {metrics['p99_error']}")
    print(f"  Within ±5 positions: {metrics['within_5_pct']}%")
    print(f"  Within ±10 positions: {metrics['within_10_pct']}%")
    print()

    # Set max_error for bounded search (use P99 + margin, capped)
    max_error = min(max(int(math.ceil(metrics["p99_error"])) + 2, 5), 20)
    print(f"  Search window set to ±{max_error} positions")

    # Export weights as JSON
    n_params = (
        weights["w1"].size + weights["b1"].size +
        weights["w2"].size + weights["b2"].size +
        weights["w3"].size + weights["b3"].size
    )

    output = {
        "architecture": f"Linear(5,{HIDDEN1}) → ReLU → Linear({HIDDEN1},{HIDDEN2}) → ReLU → Linear({HIDDEN2},1) → Sigmoid",
        "reference": "Kraska et al., 'The Case for Learned Index Structures', arXiv:1712.01208 (2017)",
        "n_parameters": int(n_params),
        "n_trajectories": n_trajectories,
        "max_error": max_error,
        "training_loss": round(float(np.mean((sigmoid(relu(relu(X @ weights["w1"].T + weights["b1"]) @ weights["w2"].T + weights["b2"]) @ weights["w3"].T + weights["b3"]) - y) ** 2)), 6),
        "metrics": metrics,
        "input_min": input_min,
        "input_max": input_max,
        "w1": weights["w1"].tolist(),
        "b1": weights["b1"].tolist(),
        "w2": weights["w2"].tolist(),
        "b2": weights["b2"].tolist(),
        "w3": weights["w3"].tolist(),
        "b3": weights["b3"].tolist(),
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    file_size_kb = os.path.getsize(OUTPUT_PATH) / 1024
    print(f"\nSaved learned index weights to {OUTPUT_PATH} ({file_size_kb:.1f} KB)")
    print(f"Total parameters: {n_params}")
    print("Done.")


if __name__ == "__main__":
    main()
