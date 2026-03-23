"""Differential privacy for maternal health analytics dashboards.

Implements the Laplace mechanism (Dwork, 2006) for epsilon-differential
privacy on aggregate health statistics. Ensures individual assessment
records cannot be inferred from published dashboard data.

The Laplace mechanism adds noise drawn from Lap(sensitivity/epsilon) to
each statistic before publication. For count queries, sensitivity = 1.

Combined with the Count-Min Sketch blood bank estimator, this creates
a double privacy layer: approximate counts + calibrated noise.

Reference:
- Dwork C, "Differential Privacy", ICALP 2006
- Dwork C & Roth A, "The Algorithmic Foundations of Differential Privacy", 2014

Applies differential privacy to maternal health dashboards, building on
prior work in privacy-preserving health analytics (e.g., COVID dashboards,
federated health data systems).

DPDP Act 2023 alignment:
- Section 8(7): Data minimization — DP ensures minimum necessary precision
- Section 4(2): Purpose limitation — aggregate stats prevent re-identification
"""

import math
import random


class DifferentialPrivacy:
    """Epsilon-differential privacy via the Laplace mechanism.

    Provides methods to privatize counts, percentages, and arbitrary
    statistics dictionaries before they are served to dashboard clients.

    Privacy is quantified by *epsilon* (the privacy budget). Smaller
    epsilon yields stronger privacy but noisier results. Each query
    consumes epsilon from the cumulative budget; once the budget is
    exhausted the caller should :meth:`reset_budget` (start a new epoch)
    to prevent unbounded privacy loss from composition.

    All randomness is generated via :class:`random.Random` so that a
    fixed seed produces reproducible output (useful for tests).

    Usage::

        dp = DifferentialPrivacy(epsilon=1.0, seed=42)
        noisy_count = dp.privatize_count(true_count=150)
        noisy_pct   = dp.privatize_percentage(true_pct=34.5, n_samples=200)
        noisy_stats = dp.privatize_stats({
            "high_risk": 42,
            "anemia_pct": 28.3,
            "district": "Patna",   # strings are passed through
        })
    """

    def __init__(self, epsilon: float = 1.0, seed: int | None = None) -> None:
        """Initialise the differential privacy engine.

        Args:
            epsilon: Privacy parameter. Must be > 0. Lower values give
                     stronger privacy (more noise). Common choices:
                     0.1 (strong), 1.0 (moderate), 10.0 (weak).
            seed:    Optional RNG seed for reproducible noise. When
                     ``None``, the system entropy source is used.

        Raises:
            ValueError: If epsilon is not positive.
        """
        if epsilon <= 0:
            raise ValueError(f"Epsilon must be positive, got {epsilon}")

        self._epsilon: float = epsilon
        self._rng: random.Random = random.Random(seed)

        # Privacy budget tracking (basic sequential composition)
        self._total_budget: float = epsilon
        self._budget_spent: float = 0.0

    @property
    def epsilon(self) -> float:
        """Return the privacy parameter epsilon."""
        return self._epsilon

    # ------------------------------------------------------------------
    # Core mechanism
    # ------------------------------------------------------------------

    def _laplace_noise(self, sensitivity: float) -> float:
        """Draw a single sample from the Laplace distribution.

        Uses the inverse-CDF method:
            noise = -(b) * sign(u - 0.5) * ln(1 - 2|u - 0.5|)
        where b = sensitivity / epsilon and u ~ Uniform(0, 1).

        Args:
            sensitivity: The L1 sensitivity of the query (maximum change
                         in the output when a single record is added or
                         removed). For counting queries this is 1.

        Returns:
            A float drawn from Lap(0, sensitivity/epsilon).
        """
        b = sensitivity / self._epsilon
        u = self._rng.random()

        # Clamp to avoid log(0) at the exact boundaries
        u = max(u, 1e-15)
        u = min(u, 1.0 - 1e-15)

        sign = 1.0 if u >= 0.5 else -1.0
        noise = -b * sign * math.log(1.0 - 2.0 * abs(u - 0.5))

        # Account for privacy budget (sequential composition theorem:
        # k queries each at epsilon cost a total of k*epsilon).
        self._budget_spent += self._epsilon

        return noise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def privatize_count(self, true_count: int, sensitivity: float = 1.0) -> int:
        """Add Laplace noise to a count and return a non-negative integer.

        Args:
            true_count:  The true count to privatize.
            sensitivity: L1 sensitivity. Defaults to 1 (single-record
                         addition/removal changes the count by at most 1).

        Returns:
            A differentially private count (>= 0).
        """
        noisy = true_count + self._laplace_noise(sensitivity)
        return max(0, round(noisy))

    def privatize_percentage(self, true_pct: float, n_samples: int) -> float:
        """Add Laplace noise to a percentage, scaled to sample size.

        The sensitivity for a percentage computed over *n* samples is
        100/n (removing one record shifts the percentage by at most
        100/n).

        Args:
            true_pct:  The true percentage (0-100).
            n_samples: Number of samples the percentage was computed
                       over. Must be >= 1.

        Returns:
            A differentially private percentage clamped to [0, 100],
            rounded to one decimal place.

        Raises:
            ValueError: If n_samples < 1.
        """
        if n_samples < 1:
            raise ValueError(f"n_samples must be >= 1, got {n_samples}")

        sensitivity = 100.0 / n_samples
        noisy = true_pct + self._laplace_noise(sensitivity)
        clamped = max(0.0, min(100.0, noisy))
        return round(clamped, 1)

    def privatize_stats(self, stats: dict) -> dict:
        """Apply differential privacy to all numeric values in a dict.

        Recursively traverses nested dicts. Integer values are treated
        as counts (sensitivity 1), floats as percentages (sensitivity 1.0).
        Non-numeric values (strings, booleans, None) are passed through
        unchanged.

        Args:
            stats: A (possibly nested) dictionary of statistics.

        Returns:
            A new dictionary with noisy numeric values.
        """
        result: dict = {}
        for key, value in stats.items():
            if isinstance(value, dict):
                result[key] = self.privatize_stats(value)
            elif isinstance(value, bool):
                # bool is a subclass of int in Python, check first
                result[key] = value
            elif isinstance(value, int):
                result[key] = self.privatize_count(value)
            elif isinstance(value, float):
                # Treat as a general real-valued statistic with
                # sensitivity 1.0.  Clamp to >= 0 and round to 1 dp.
                noisy = value + self._laplace_noise(1.0)
                result[key] = round(max(0.0, noisy), 1)
            elif isinstance(value, str):
                result[key] = value
            else:
                # Lists, None, etc. — pass through
                result[key] = value
        return result

    def privacy_budget_remaining(self) -> float:
        """Return the remaining privacy budget.

        Under sequential composition, the total privacy cost is the sum
        of the epsilon spent on each query. This method returns how much
        of the original budget has *not* been consumed.

        Returns:
            Remaining budget as a float. Can go negative if the budget
            has been exceeded (the caller should :meth:`reset_budget`).
        """
        return self._total_budget - self._budget_spent

    def reset_budget(self) -> None:
        """Reset the privacy budget for a new epoch.

        In practice an "epoch" might correspond to a dashboard refresh
        interval (e.g. daily). Resetting the budget is valid when the
        underlying dataset has changed enough that previous queries are
        no longer correlated with the new data.
        """
        self._budget_spent = 0.0
