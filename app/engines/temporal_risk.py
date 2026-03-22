"""Temporal maternal risk trajectory engine.

Generates week-by-week risk score trajectories by iteratively evaluating
the multiplicative relative risk model from current gestational week through
week 42, using the anemia prediction engine's hemoglobin trajectory as a
dynamic input for the hemoglobin risk factor.

This identifies the "risk crossover week" — the gestational week when the
patient is predicted to transition to a higher risk level — enabling
proactive intervention scheduling.

Applies precomputed temporal risk trajectories that dynamically couple a
multiplicative RR model with a learned-index-based anemia trajectory
prediction, building on prior work in dynamic risk scoring for obstetrics.
"""

from typing import Optional

from app.engines.risk_scoring import RiskScoringEngine
from app.engines.anemia_prediction import AnemiaPredictionEngine


# Risk levels ordered from lowest to highest severity
_RISK_LEVEL_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class TemporalRiskEngine:
    """Week-by-week maternal risk trajectory with dynamic Hb coupling.

    Couples the multiplicative relative risk model (RiskScoringEngine) with
    the learned-index-based hemoglobin trajectory prediction (AnemiaPredictionEngine)
    to produce a temporal risk curve from the current gestational week through
    week 42.

    Key output: the "risk crossover week" — the first future week when the
    patient's risk level is predicted to worsen — which enables ASHA workers
    to schedule interventions proactively rather than reactively.

    Complexity: O(W) where W = (42 - current_week), with each week requiring
    one O(1) risk scoring lookup and one O(1) Hb trajectory read.
    """

    def __init__(
        self,
        risk_engine: RiskScoringEngine,
        anemia_engine: AnemiaPredictionEngine,
    ):
        self._risk_engine = risk_engine
        self._anemia_engine = anemia_engine

    def compute_trajectory(
        self,
        age: int,
        parity: int,
        hemoglobin: float,
        bp_systolic: int,
        bp_diastolic: int,
        gestational_weeks: int,
        height_cm: float,
        weight_kg: float,
        complication_history: str,
        ifa_compliance: float = 0.5,
        dietary_score: float = 0.5,
        prev_anemia: bool = False,
    ) -> dict:
        """Compute week-by-week risk trajectory from current week through week 42.

        Procedure:
          1. Obtain the Hb trajectory from the anemia prediction engine,
             which provides predicted hemoglobin values for each future week.
          2. For each week from current gestational week to 42, re-score the
             patient using the risk engine with that week's predicted Hb,
             holding all other clinical parameters constant.
          3. Identify the peak risk week, the risk crossover week (first week
             where risk level worsens), and the intervention window.

        Returns:
            dict with keys:
                trajectory: list of {week, risk_score, risk_level, predicted_hb}
                peak_risk_week: int — week with highest risk score
                risk_crossover_week: int or None — first week risk level increases
                intervention_window: int — weeks between now and crossover (or peak)
                current_risk_level: str — risk level at current gestational week
                projected_worst_risk_level: str — highest risk level in trajectory
        """
        # --- Step 1: Get Hb trajectory from anemia engine ---
        anemia_result = self._anemia_engine.predict(
            initial_hb=hemoglobin,
            gestational_weeks=gestational_weeks,
            ifa_compliance=ifa_compliance,
            dietary_score=dietary_score,
            prev_anemia=prev_anemia,
        )

        # Build a week -> predicted_hb lookup from the anemia trajectory.
        # The anemia engine returns trajectory entries as {week, predicted_hb}.
        hb_by_week: dict[int, float] = {}
        for entry in anemia_result.get("trajectory", []):
            hb_by_week[entry["week"]] = entry["predicted_hb"]

        # --- Step 2: Score each week from current through 42 ---
        trajectory: list[dict] = []
        peak_risk_score = -1.0
        peak_risk_week = gestational_weeks
        current_risk_level: Optional[str] = None
        projected_worst_level = "low"
        risk_crossover_week: Optional[int] = None
        previous_risk_level: Optional[str] = None

        for week in range(gestational_weeks, 43):  # inclusive of week 42
            # Use predicted Hb for this week; fall back to initial Hb if not available
            week_hb = hb_by_week.get(week, hemoglobin)

            # Re-score with this week's gestational age and predicted Hb
            week_result = self._risk_engine.score(
                age=age,
                parity=parity,
                hemoglobin=week_hb,
                bp_systolic=bp_systolic,
                bp_diastolic=bp_diastolic,
                gestational_weeks=week,
                height_cm=height_cm,
                weight_kg=weight_kg,
                complication_history=complication_history,
                ifa_compliance=ifa_compliance,
                dietary_score=dietary_score,
                prev_anemia=prev_anemia,
            )

            week_score = week_result["risk_score"]
            week_level = week_result["risk_level"]

            trajectory.append({
                "week": week,
                "risk_score": week_score,
                "risk_level": week_level,
                "predicted_hb": week_hb,
            })

            # Track peak risk
            if week_score > peak_risk_score:
                peak_risk_score = week_score
                peak_risk_week = week

            # Track worst projected level
            if _RISK_LEVEL_ORDER.get(week_level, 0) > _RISK_LEVEL_ORDER.get(
                projected_worst_level, 0
            ):
                projected_worst_level = week_level

            # Record current risk level (first week in the trajectory)
            if current_risk_level is None:
                current_risk_level = week_level

            # Detect risk crossover: first week where level worsens vs. previous week
            if previous_risk_level is not None and risk_crossover_week is None:
                if _RISK_LEVEL_ORDER.get(week_level, 0) > _RISK_LEVEL_ORDER.get(
                    previous_risk_level, 0
                ):
                    risk_crossover_week = week

            previous_risk_level = week_level

        # --- Step 3: Compute intervention window ---
        # Window = weeks between now and the crossover week (or peak if no crossover)
        reference_week = (
            risk_crossover_week if risk_crossover_week is not None else peak_risk_week
        )
        intervention_window = max(0, reference_week - gestational_weeks)

        return {
            "trajectory": trajectory,
            "peak_risk_week": peak_risk_week,
            "risk_crossover_week": risk_crossover_week,
            "intervention_window": intervention_window,
            "current_risk_level": current_risk_level or "low",
            "projected_worst_risk_level": projected_worst_level,
        }
