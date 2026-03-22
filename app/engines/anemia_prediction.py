import json
import math
from typing import Optional

from app.engines.learned_index import LearnedIndex


class AnemiaPredictionEngine:
    """O(1) anemia progression prediction via learned index on hemoglobin trajectories.

    Uses a learned index structure (Kraska et al., 2017) — a 2-layer MLP (5→64→32→1)
    that approximates the CDF of sorted hemoglobin trajectories — to predict the
    position of the best-matching trajectory from raw continuous features in O(1) time.
    Local binary search over ±max_error positions refines the match (O(1) bounded).

    Falls back to hash-based discretized lookup or analytical computation when
    the learned index is not available.

    Physiological model calibrated from:
    - WHO 2012: Daily iron and folic acid supplementation guideline
    - Bothwell TH (2000): Iron requirements in pregnancy, Am J Clin Nutr
    - NFHS-5 (2019-21): Anemia prevalence - 52.2% pregnant women anemic
    - WHO: Haemoglobin concentrations for diagnosis of anaemia (2011)

    Learned index reference:
    - Kraska T et al., "The Case for Learned Index Structures", arXiv:1712.01208 (2017)
    """

    # WHO pregnancy hemoglobin thresholds
    # Source: WHO, "Haemoglobin concentrations for the diagnosis of anaemia", 2011 (WHO/NMH/NHD/MNM/11.1)
    SEVERE_ANEMIA = 7.0    # WHO 2011: severe anemia in pregnancy (<7 g/dL)
    MODERATE_ANEMIA = 10.0  # WHO 2011: moderate anemia in pregnancy (7.0-9.9 g/dL)
    MILD_ANEMIA = 11.0     # WHO 2011: mild anemia in pregnancy (10.0-10.9 g/dL)
    NORMAL_HB = 11.0       # WHO 2011: normal hemoglobin in pregnancy (>=11.0 g/dL)

    def __init__(self):
        self._trajectories: list[dict] = []
        self._index: dict[str, int] = {}  # feature_key -> position in sorted array
        self._learned_index: Optional[LearnedIndex] = None
        self._loaded = False

    def load(self, path: str) -> None:
        """Load precomputed trajectory array and lookup index."""
        with open(path) as f:
            data = json.load(f)
        self._trajectories = data["trajectories"]
        self._index = data["index"]
        self._loaded = True

        # Load learned index if available (optional enhancement)
        learned_index_path = path.replace("hb_trajectories.json", "learned_index_weights.json")
        try:
            self._learned_index = LearnedIndex()
            self._learned_index.load(learned_index_path)
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            self._learned_index = None

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
        """O(1) hemoglobin trajectory prediction via learned index.

        Primary path: Learned index MLP predicts approximate position in sorted
        trajectory array → local search over ±max_error positions for best match.
        Fallback 1: Hash-based discretized index lookup.
        Fallback 2: Analytical physiological model computation.

        Returns dict with: current_hb, predicted_delivery_hb, trajectory,
        risk_level, intervention_urgency, compliance_impact
        """
        # Primary: Learned index (O(1) — MLP inference + bounded local search)
        if self._learned_index is not None and self._learned_index.is_loaded:
            traj = self._learned_index_lookup(
                initial_hb, gestational_weeks, ifa_compliance,
                dietary_score, prev_anemia
            )
            if traj is not None:
                return self._format_result(traj, initial_hb, gestational_weeks, ifa_compliance)

        # Fallback 1: Hash-based discretized index
        key = self._discretize_features(initial_hb, gestational_weeks,
                                         ifa_compliance, dietary_score, prev_anemia)
        if key in self._index:
            pos = self._index[key]
            if 0 <= pos < len(self._trajectories):
                traj = self._trajectories[pos]
                return self._format_result(traj, initial_hb, gestational_weeks, ifa_compliance)

        # Fallback 2: Analytical physiological model
        return self._compute_trajectory(initial_hb, gestational_weeks,
                                         ifa_compliance, dietary_score, prev_anemia)

    def _learned_index_lookup(self, initial_hb: float, gest_weeks: int,
                               ifa_compliance: float, dietary_score: float,
                               prev_anemia: bool) -> Optional[dict]:
        """Use learned index MLP to find best-matching precomputed trajectory.

        The MLP predicts approximate position in the sorted trajectory array
        directly from input features. Local search over +/-max_error positions
        finds the closest match by comparing INPUT features (not analytical output),
        avoiding redundant analytical computation.
        """
        predicted_pos = self._learned_index.predict_position(
            initial_hb, gest_weeks, ifa_compliance, dietary_score, prev_anemia
        )
        lo, hi = self._learned_index.search_window(predicted_pos)

        if not self._trajectories:
            return None

        # Input feature vector for comparison
        query_features = [
            initial_hb,
            float(gest_weeks),
            ifa_compliance,
            dietary_score,
            1.0 if prev_anemia else 0.0,
        ]

        # Local search: find trajectory with closest INPUT features
        best_pos = predicted_pos
        best_diff = float("inf")
        for pos in range(lo, hi + 1):
            if 0 <= pos < len(self._trajectories):
                traj = self._trajectories[pos]
                # Compare by input features stored in each trajectory profile
                diff = (
                    abs(traj.get("initial_hb", 0) - query_features[0])
                    + abs(traj.get("gest_weeks", 0) - query_features[1]) / 40.0
                    + abs(traj.get("ifa_compliance", 0) - query_features[2])
                    + abs(traj.get("dietary_score", 0) - query_features[3])
                    + abs((1.0 if traj.get("prev_anemia", False) else 0.0) - query_features[4])
                )
                if diff < best_diff:
                    best_diff = diff
                    best_pos = pos

        if 0 <= best_pos < len(self._trajectories):
            return self._trajectories[best_pos]
        return None

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
        # Bothwell TH, "Iron requirements in pregnancy and strategies to meet them",
        # Am J Clin Nutr 2000;72(1):257S-264S
        base_decline_per_week = 0.04  # 0.04 g/dL/week — Bothwell TH, Am J Clin Nutr 2000

        # IFA supplementation effect:
        # Peña-Rosas JP et al, Cochrane Database Syst Rev 2015;(7):CD004736
        # 30-60mg elemental iron daily
        ifa_effect = ifa_compliance * 0.03  # 0.03 g/dL/week — Peña-Rosas et al, Cochrane 2015

        # Dietary iron contribution:
        # Haider BA, Bhutta ZA, Cochrane Database Syst Rev 2017;(4):CD004905
        # Bioavailable iron from mixed Indian diet ~3-5 mg/day
        diet_effect = dietary_score * 0.015  # 0.015 g/dL/week — Haider & Bhutta, Cochrane 2017

        # Previous anemia increases vulnerability:
        # Badfar G et al, J Matern Fetal Neonatal Med 2017;30(17):2097-2109 (recurrence risk elevation)
        anemia_penalty = 0.015 if prev_anemia else 0.0  # 0.015 g/dL/week — Badfar et al 2017

        # Net weekly change
        net_decline = base_decline_per_week - ifa_effect - diet_effect + anemia_penalty

        # Generate week-by-week trajectory
        trajectory = []
        current_hb = initial_hb

        for week in range(gest_weeks, 42):
            # Hemodilution effect peaks at 28-34 weeks
            hemodilution = 0.0
            if 20 <= week <= 34:
                # Gaussian-shaped hemodilution centered at week 30, peak 0.03 g/dL
                # Hytten F, "Blood volume changes in normal pregnancy", Clin Haematol 1985;14(3):601-612
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
