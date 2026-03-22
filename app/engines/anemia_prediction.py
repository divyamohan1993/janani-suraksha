import json
import math
from typing import Optional


class AnemiaPredictionEngine:
    """O(1) anemia progression prediction via learned index on hemoglobin trajectories.

    Maps maternal health features to position in sorted array of historical
    hemoglobin trajectories. Predicts future Hb levels and intervention urgency.

    Physiological model calibrated from:
    - WHO 2012: Daily iron and folic acid supplementation guideline
    - Bothwell TH (2000): Iron requirements in pregnancy, Am J Clin Nutr
    - NFHS-5 (2019-21): Anemia prevalence - 52.2% pregnant women anemic
    - WHO: Haemoglobin concentrations for diagnosis of anaemia (2011)
    """

    # WHO pregnancy hemoglobin thresholds
    SEVERE_ANEMIA = 7.0
    MODERATE_ANEMIA = 9.0
    MILD_ANEMIA = 11.0
    NORMAL_HB = 12.0

    def __init__(self):
        self._trajectories: list[dict] = []
        self._index: dict[str, int] = {}  # feature_key -> position in sorted array
        self._loaded = False

    def load(self, path: str) -> None:
        """Load precomputed trajectory array and learned index."""
        with open(path) as f:
            data = json.load(f)
        self._trajectories = data["trajectories"]
        self._index = data["index"]
        self._loaded = True

    @staticmethod
    def _discretize_features(initial_hb: float, gest_weeks: int,
                              ifa_compliance: float, dietary_score: float,
                              prev_anemia: bool) -> str:
        """Discretize input features into lookup key."""
        # Discretize each dimension
        hb_bucket = min(int((initial_hb - 3.0) / 1.0), 16)  # 1 g/dL buckets, 3-19
        hb_bucket = max(0, hb_bucket)

        gest_bucket = min(gest_weeks // 4, 10)  # 4-week buckets, 0-40

        ifa_bucket = min(int(ifa_compliance * 4), 4)  # 0, 0.25, 0.5, 0.75, 1.0

        diet_bucket = min(int(dietary_score * 3), 3)  # 0, 0.33, 0.67, 1.0

        anemia_flag = 1 if prev_anemia else 0

        return f"{hb_bucket}:{gest_bucket}:{ifa_bucket}:{diet_bucket}:{anemia_flag}"

    def predict(self, initial_hb: float, gestational_weeks: int,
                ifa_compliance: float, dietary_score: float,
                prev_anemia: bool) -> dict:
        """O(1) hemoglobin trajectory prediction.

        Returns dict with: current_hb, predicted_delivery_hb, trajectory,
        risk_level, intervention_urgency, compliance_impact
        """
        key = self._discretize_features(initial_hb, gestational_weeks,
                                         ifa_compliance, dietary_score, prev_anemia)

        # O(1) index lookup
        if key in self._index:
            pos = self._index[key]
            if 0 <= pos < len(self._trajectories):
                traj = self._trajectories[pos]
                return self._format_result(traj, initial_hb, gestational_weeks, ifa_compliance)

        # Fallback: compute trajectory analytically
        return self._compute_trajectory(initial_hb, gestational_weeks,
                                         ifa_compliance, dietary_score, prev_anemia)

    def _compute_trajectory(self, initial_hb: float, gest_weeks: int,
                            ifa_compliance: float, dietary_score: float,
                            prev_anemia: bool) -> dict:
        """Compute Hb trajectory analytically (fallback and precomputation base)."""

        # WHO-calibrated physiological parameters
        # Source: WHO Guideline on daily iron and folic acid supplementation (2012)
        # Source: Bothwell TH, "Iron requirements in pregnancy", Am J Clin Nutr (2000)

        # Physiological Hb decline during pregnancy:
        # - Plasma volume expands 40-50% by week 30-34
        # - RBC mass increases only 20-30%
        # - Net effect: ~1.5 g/dL Hb drop at nadir (week 28-34)
        base_decline_per_week = 0.04  # WHO reference: ~0.04 g/dL/week average decline

        # IFA supplementation effect:
        # WHO meta-analysis: 30-60mg daily iron increases Hb by 0.03 g/dL/week
        ifa_effect = ifa_compliance * 0.03

        # Dietary iron contribution:
        # Bioavailable iron from Indian diet: ~3-5mg/day (Plant-based diet absorption ~5%)
        diet_effect = dietary_score * 0.015

        # Previous anemia increases vulnerability:
        # NFHS-5: women with history of anemia have 1.5x risk of recurrence
        anemia_penalty = 0.015 if prev_anemia else 0.0

        # Net weekly change
        net_decline = base_decline_per_week - ifa_effect - diet_effect + anemia_penalty

        # Generate week-by-week trajectory
        trajectory = []
        current_hb = initial_hb

        for week in range(gest_weeks, 42):
            # Hemodilution effect peaks at 28-34 weeks
            hemodilution = 0.0
            if 20 <= week <= 34:
                # Gaussian-shaped hemodilution centered at week 30
                hemodilution = 0.03 * math.exp(-0.5 * ((week - 30) / 4) ** 2)

            current_hb = max(3.0, current_hb - net_decline - hemodilution)
            trajectory.append({"week": week, "predicted_hb": round(current_hb, 1)})

        predicted_delivery_hb = trajectory[-1]["predicted_hb"] if trajectory else initial_hb

        # Compute compliance impact scenarios
        # With 90% compliance
        hb_with_compliance = initial_hb
        for week in range(gest_weeks, 42):
            hemodilution = 0.03 * math.exp(-0.5 * ((week - 30) / 4) ** 2) if 20 <= week <= 34 else 0.0
            decline = base_decline_per_week - 0.9 * 0.03 - dietary_score * 0.015 + anemia_penalty - hemodilution
            hb_with_compliance = max(3.0, hb_with_compliance - decline)

        # Without compliance
        hb_without = initial_hb
        for week in range(gest_weeks, 42):
            hemodilution = 0.03 * math.exp(-0.5 * ((week - 30) / 4) ** 2) if 20 <= week <= 34 else 0.0
            decline = base_decline_per_week - 0.0 * 0.03 - dietary_score * 0.015 + anemia_penalty + hemodilution
            hb_without = max(3.0, hb_without - decline)

        # Determine risk level
        if predicted_delivery_hb < self.SEVERE_ANEMIA:
            risk_level = "critical"
            urgency = "emergency"
        elif predicted_delivery_hb < self.MODERATE_ANEMIA:
            risk_level = "high"
            urgency = "urgent"
        elif predicted_delivery_hb < self.MILD_ANEMIA:
            risk_level = "medium"
            urgency = "soon"
        else:
            risk_level = "low"
            urgency = "routine"

        return {
            "current_hb": round(initial_hb, 1),
            "predicted_delivery_hb": round(predicted_delivery_hb, 1),
            "trajectory": trajectory,
            "risk_level": risk_level,
            "intervention_urgency": urgency,
            "compliance_impact": {
                "with_90pct_compliance": round(hb_with_compliance, 1),
                "without_compliance": round(hb_without, 1),
            }
        }

    def _format_result(self, traj: dict, initial_hb: float,
                       gest_weeks: int, ifa_compliance: float) -> dict:
        """Format a precomputed trajectory into the standard result."""
        return {
            "current_hb": round(initial_hb, 1),
            "predicted_delivery_hb": traj["predicted_delivery_hb"],
            "trajectory": traj["trajectory"],
            "risk_level": traj["risk_level"],
            "intervention_urgency": traj["intervention_urgency"],
            "compliance_impact": traj["compliance_impact"],
        }

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def trajectory_count(self) -> int:
        return len(self._trajectories)
