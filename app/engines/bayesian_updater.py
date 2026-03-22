"""In-memory Bayesian posterior updater for risk scoring.

Implements the conjugate Beta-Binomial update:
  Prior:     Beta(alpha_0, beta_0)  --- from static risk table
  Posterior: Beta(alpha_0 + s, beta_0 + n - s)
  where s = observed adverse outcomes, n = total observed outcomes

Outcomes accumulate in memory during container lifetime.
On restart, resets to static table (stateless container design).
Future versions will persist to Firestore/BigQuery for durable learning.

This enables the continuous Bayesian learning loop described in the patent:
  Risk table -> ASHA assessment -> Hospital delivery -> Outcome recorded ->
  Posterior updated -> Risk table improves -> Better predictions
"""

import threading
from typing import Optional
from app.engines.risk_scoring import RiskScoringEngine


class BayesianUpdater:
    """Thread-safe in-memory Bayesian posterior updater.

    Wraps RiskScoringEngine and applies posterior corrections
    based on recorded birth outcomes.
    """

    def __init__(self, risk_engine: RiskScoringEngine):
        self._engine = risk_engine
        # Accumulator: hash_key -> {"adverse": int, "total": int}
        self._outcomes: dict[str, dict[str, int]] = {}
        self._lock = threading.Lock()

    def record_outcome(self, age: int, parity: int, hemoglobin: float,
                       bp_systolic: int, bp_diastolic: int,
                       gestational_weeks: int, height_cm: float,
                       weight_kg: float, complication_history: str,
                       adverse_outcome: bool) -> dict:
        """Record a birth outcome for Bayesian posterior updating.

        Args:
            adverse_outcome: True if adverse maternal outcome occurred
                           (hemorrhage, eclampsia, sepsis, maternal death, etc.)

        Returns:
            dict with prior and posterior risk scores showing the update effect
        """
        # Compute the hash key for this risk factor combination
        age_idx = self._engine._discretize_age(age)
        parity_idx = self._engine._discretize_parity(parity)
        hb_idx = self._engine._discretize_hb(hemoglobin)
        bp_idx = self._engine._discretize_bp(bp_systolic, bp_diastolic)
        gest_idx = self._engine._discretize_gestational_weeks(gestational_weeks)
        bmi_idx = self._engine._discretize_bmi(height_cm, weight_kg)
        comp_idx = self._engine._discretize_complication(complication_history)

        key = self._engine._compute_hash(
            age_idx, parity_idx, hb_idx, bp_idx, gest_idx, bmi_idx, comp_idx
        )

        # Get prior score (from static table)
        prior_result = self._engine.score(
            age=age, parity=parity, hemoglobin=hemoglobin,
            bp_systolic=bp_systolic, bp_diastolic=bp_diastolic,
            gestational_weeks=gestational_weeks,
            height_cm=height_cm, weight_kg=weight_kg,
            complication_history=complication_history,
        )
        prior_alpha = prior_result["alpha"]
        prior_beta = prior_result["beta"]

        # Update accumulator (thread-safe)
        with self._lock:
            if key not in self._outcomes:
                self._outcomes[key] = {"adverse": 0, "total": 0}
            self._outcomes[key]["total"] += 1
            if adverse_outcome:
                self._outcomes[key]["adverse"] += 1

            s = self._outcomes[key]["adverse"]
            n = self._outcomes[key]["total"]

        # Compute posterior: Beta(alpha_0 + s, beta_0 + n - s)
        posterior_alpha = prior_alpha + s
        posterior_beta = prior_beta + (n - s)
        posterior_risk = posterior_alpha / (posterior_alpha + posterior_beta)

        # Classify
        if posterior_risk >= 0.15:
            posterior_level = "critical"
        elif posterior_risk >= 0.05:
            posterior_level = "high"
        elif posterior_risk >= 0.01:
            posterior_level = "medium"
        else:
            posterior_level = "low"

        return {
            "key": key,
            "prior": {
                "alpha": round(prior_alpha, 2),
                "beta": round(prior_beta, 2),
                "risk_score": round(prior_alpha / (prior_alpha + prior_beta), 4),
            },
            "observed": {"adverse": s, "total": n},
            "posterior": {
                "alpha": round(posterior_alpha, 2),
                "beta": round(posterior_beta, 2),
                "risk_score": round(posterior_risk, 4),
                "risk_level": posterior_level,
            },
            "update_effect": round(posterior_risk - prior_alpha / (prior_alpha + prior_beta), 4),
        }

    def get_posterior_adjustment(self, key: str) -> Optional[dict]:
        """Get posterior adjustment for a given risk factor hash key."""
        with self._lock:
            if key not in self._outcomes:
                return None
            outcome = self._outcomes[key]
        return {"adverse": outcome["adverse"], "total": outcome["total"]}

    def score_with_posterior(self, age: int, parity: int, hemoglobin: float,
                             bp_systolic: int, bp_diastolic: int,
                             gestational_weeks: int, height_cm: float,
                             weight_kg: float, complication_history: str,
                             **kwargs) -> dict:
        """Score with Bayesian posterior correction applied.

        If outcomes have been recorded for this risk factor combination,
        the posterior risk score incorporates observed outcome data.
        """
        result = self._engine.score(
            age=age, parity=parity, hemoglobin=hemoglobin,
            bp_systolic=bp_systolic, bp_diastolic=bp_diastolic,
            gestational_weeks=gestational_weeks,
            height_cm=height_cm, weight_kg=weight_kg,
            complication_history=complication_history,
            **kwargs,
        )

        # Compute hash key
        age_idx = self._engine._discretize_age(age)
        parity_idx = self._engine._discretize_parity(parity)
        hb_idx = self._engine._discretize_hb(hemoglobin)
        bp_idx = self._engine._discretize_bp(bp_systolic, bp_diastolic)
        gest_idx = self._engine._discretize_gestational_weeks(gestational_weeks)
        bmi_idx = self._engine._discretize_bmi(height_cm, weight_kg)
        comp_idx = self._engine._discretize_complication(complication_history)
        key = self._engine._compute_hash(
            age_idx, parity_idx, hb_idx, bp_idx, gest_idx, bmi_idx, comp_idx
        )

        adjustment = self.get_posterior_adjustment(key)
        if adjustment and adjustment["total"] > 0:
            s = adjustment["adverse"]
            n = adjustment["total"]
            prior_alpha = result["alpha"]
            prior_beta = result["beta"]

            posterior_alpha = prior_alpha + s
            posterior_beta = prior_beta + (n - s)
            posterior_risk = posterior_alpha / (posterior_alpha + posterior_beta)
            posterior_risk = min(posterior_risk, 0.95)

            result["alpha"] = round(posterior_alpha, 2)
            result["beta"] = round(posterior_beta, 2)
            result["risk_score"] = round(posterior_risk, 4)
            result["bayesian_update"] = {
                "outcomes_observed": n,
                "adverse_observed": s,
                "prior_risk": round(prior_alpha / (prior_alpha + prior_beta), 4),
                "posterior_risk": round(posterior_risk, 4),
            }

            # Reclassify
            if posterior_risk >= 0.15:
                result["risk_level"] = "critical"
            elif posterior_risk >= 0.05:
                result["risk_level"] = "high"
            elif posterior_risk >= 0.01:
                result["risk_level"] = "medium"
            else:
                result["risk_level"] = "low"

        return result

    @property
    def outcomes_recorded(self) -> int:
        with self._lock:
            return sum(o["total"] for o in self._outcomes.values())

    @property
    def unique_combinations_observed(self) -> int:
        with self._lock:
            return len(self._outcomes)
