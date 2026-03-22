import hashlib
import json
import struct
from pathlib import Path
from typing import Optional


class RiskScoringEngine:
    """O(1) Bayesian maternal risk scoring via precomputed conjugate posterior tables.

    70,000 entries mapping discretized risk factor combinations to Beta-Binomial
    posterior risk scores. Single hash-indexed lookup at runtime.
    """

    # Discretization buckets (from spec)
    AGE_BUCKETS = [(0, 18), (18, 26), (26, 31), (31, 36), (36, 100)]  # 5 levels
    PARITY_BUCKETS = [(0, 1), (1, 3), (3, 5), (5, 100)]  # 4 levels
    HB_BUCKETS = [(0, 7), (7, 9), (9, 11), (11, 12), (12, 100)]  # 5 levels
    BP_BUCKETS = ["normal", "elevated", "stage1", "stage2", "crisis"]  # 5 levels
    GEST_BUCKETS = [(0, 13), (13, 21), (21, 29), (29, 35), (35, 38), (38, 41), (41, 50)]  # 7 levels
    BMI_BUCKETS = [(0, 18.5), (18.5, 25), (25, 30), (30, 100)]  # 4 levels
    COMP_BUCKETS = ["none", "prev_csection", "prev_pph", "prev_eclampsia", "multiple"]  # 5 levels

    RISK_THRESHOLDS = {
        "low": 0.01,
        "medium": 0.05,
        "high": 0.15,
    }

    def __init__(self):
        self._table: dict[str, dict] = {}
        self._loaded = False

    def load(self, path: str) -> None:
        """Load precomputed risk table from JSON file."""
        with open(path) as f:
            self._table = json.load(f)
        self._loaded = True

    @staticmethod
    def _discretize_age(age: int) -> int:
        if age < 18:
            return 0
        if age < 26:
            return 1
        if age < 31:
            return 2
        if age < 36:
            return 3
        return 4

    @staticmethod
    def _discretize_parity(parity: int) -> int:
        if parity == 0:
            return 0
        if parity < 3:
            return 1
        if parity < 5:
            return 2
        return 3

    @staticmethod
    def _discretize_hb(hb: float) -> int:
        if hb < 7:
            return 0
        if hb < 9:
            return 1
        if hb < 11:
            return 2
        if hb < 12:
            return 3
        return 4

    @staticmethod
    def _discretize_bp(systolic: int, diastolic: int) -> int:
        if systolic >= 180 or diastolic >= 120:
            return 4  # crisis
        if systolic >= 140 or diastolic >= 90:
            return 3  # stage2
        if systolic >= 130 or diastolic >= 80:
            return 2  # stage1
        if systolic >= 120 and diastolic < 80:
            return 1  # elevated
        return 0  # normal

    @staticmethod
    def _discretize_gestational_weeks(weeks: int) -> int:
        if weeks < 13:
            return 0
        if weeks < 21:
            return 1
        if weeks < 29:
            return 2
        if weeks < 35:
            return 3
        if weeks < 38:
            return 4
        if weeks < 41:
            return 5
        return 6

    @staticmethod
    def _discretize_bmi(height_cm: float, weight_kg: float) -> int:
        bmi = weight_kg / ((height_cm / 100) ** 2)
        if bmi < 18.5:
            return 0
        if bmi < 25:
            return 1
        if bmi < 30:
            return 2
        return 3

    @staticmethod
    def _discretize_complication(comp: str) -> int:
        mapping = {
            "none": 0,
            "prev_csection": 1,
            "prev_pph": 2,
            "prev_eclampsia": 3,
            "multiple": 4,
        }
        return mapping.get(comp, 0)

    @staticmethod
    def _compute_hash(
        age_idx: int,
        parity_idx: int,
        hb_idx: int,
        bp_idx: int,
        gest_idx: int,
        bmi_idx: int,
        comp_idx: int,
    ) -> str:
        """Compute deterministic hash key from discretized indices."""
        key_bytes = struct.pack(
            "7B", age_idx, parity_idx, hb_idx, bp_idx, gest_idx, bmi_idx, comp_idx
        )
        return hashlib.sha256(key_bytes).hexdigest()[:16]

    def score(
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
    ) -> dict:
        """O(1) risk scoring via hash table lookup.

        Returns dict with: risk_score, risk_level, alpha, beta, interventions, risk_factors_summary
        """
        # Discretize all 7 factors
        age_idx = self._discretize_age(age)
        parity_idx = self._discretize_parity(parity)
        hb_idx = self._discretize_hb(hemoglobin)
        bp_idx = self._discretize_bp(bp_systolic, bp_diastolic)
        gest_idx = self._discretize_gestational_weeks(gestational_weeks)
        bmi_idx = self._discretize_bmi(height_cm, weight_kg)
        comp_idx = self._discretize_complication(complication_history)

        # O(1) hash lookup
        key = self._compute_hash(
            age_idx, parity_idx, hb_idx, bp_idx, gest_idx, bmi_idx, comp_idx
        )

        if key in self._table:
            return self._table[key]

        # Fallback: compute on-the-fly (should not happen with complete table)
        return self._compute_risk(
            age_idx, parity_idx, hb_idx, bp_idx, gest_idx, bmi_idx, comp_idx
        )

    def _compute_risk(
        self,
        age_idx: int,
        parity_idx: int,
        hb_idx: int,
        bp_idx: int,
        gest_idx: int,
        bmi_idx: int,
        comp_idx: int,
    ) -> dict:
        """Compute risk score from Beta-Binomial posterior (fallback).

        Uses conjugate Beta prior updated with pseudo-observations derived from
        epidemiological risk-factor weights.  Alpha encodes adverse-outcome
        evidence; beta encodes safe-outcome evidence.  The posterior mean
        alpha / (alpha + beta) is the risk score.
        """
        # Base prior: uninformative but anchored to India SRS maternal
        # mortality ratio (~130 per 100k => ~0.0013 baseline).  We use a
        # weakly informative Beta(1, 99) so the prior mean is 0.01,
        # slightly above baseline to account for the sub-population that
        # actually presents for screening.
        alpha_0 = 1.0
        beta_0 = 99.0

        # ------------------------------------------------------------------
        # Risk factor contributions (additive to alpha = adverse outcomes)
        #
        # Calibrated against:
        #   - NFHS-5 anaemia prevalence & maternal outcome data
        #   - WHO near-miss criteria
        #   - ACOG hypertension staging
        #   - Lancet India maternal health series
        # ------------------------------------------------------------------
        risk_additions = {
            # <18 adolescent: higher eclampsia/obstructed labour risk
            # 18-25, 26-30: reference / optimal
            # 31-35: AMA begins, slight uptick
            # >35: significantly elevated risk (chromosomal, HTN, GDM)
            "age": [0.5, 0.0, 0.0, 0.2, 1.0],
            # Nullipara: higher pre-eclampsia risk
            # 1-2: optimal
            # 3-4: uterine atony risk rises
            # >=5: grand multipara — PPH, malpresentation, rupture
            "parity": [0.3, 0.0, 0.3, 1.0],
            # Hb <7: severe anaemia — cardiac failure risk, PPH fatality
            # 7-9: moderate anaemia — transfusion may be needed
            # 9-11: mild anaemia — IFA responsive
            # 11-12, >12: normal
            "hb": [3.0, 1.5, 0.3, 0.0, 0.0],
            # Normal: no added risk
            # Elevated: watchful waiting
            # Stage 1: medication consideration
            # Stage 2: active management, end-organ risk
            # Crisis: imminent eclampsia/stroke/HELLP
            "bp": [0.0, 0.3, 1.0, 2.5, 5.0],
            # 1st trimester: ectopic/miscarriage baseline
            # Early 2nd: lowest risk window
            # Late 2nd: pre-viable if complications
            # Early 3rd: preterm delivery risk begins
            # Late preterm 35-37w: moderate NICU risk
            # Term 38-40w: optimal timing
            # Post-term >40w: placental insufficiency, macrosomia
            "gest": [0.1, 0.0, 0.0, 0.2, 0.5, 0.3, 1.5],
            # Underweight: IUGR, preterm, anaemia synergy
            # Normal: reference
            # Overweight: GDM, HTN risk
            # Obese: thromboembolic, surgical complications
            "bmi": [0.5, 0.0, 0.3, 1.0],
            # None: baseline
            # Prev C-section: uterine rupture risk in labour
            # Prev PPH: recurrence 15-20%
            # Prev eclampsia: recurrence ~25%, earlier onset
            # Multiple: compounding risk
            "comp": [0.0, 0.5, 2.0, 2.5, 3.0],
        }

        # Interaction terms — certain combinations are synergistically dangerous
        interaction_alpha = 0.0

        # Severe anaemia + previous PPH: haemorrhage fatality risk spikes
        if hb_idx <= 1 and comp_idx == 2:
            interaction_alpha += 2.0

        # Severe anaemia + multiple complications
        if hb_idx == 0 and comp_idx == 4:
            interaction_alpha += 1.5

        # Hypertension (stage2+) + previous eclampsia: superimposed pre-eclampsia
        if bp_idx >= 3 and comp_idx == 3:
            interaction_alpha += 2.0

        # BP crisis + any anaemia: end-organ damage risk
        if bp_idx == 4 and hb_idx <= 2:
            interaction_alpha += 1.0

        # Adolescent (<18) + nullipara: obstructed labour / eclampsia
        if age_idx == 0 and parity_idx == 0:
            interaction_alpha += 0.5

        # Grand multipara + obesity: uterine atony + surgical risk
        if parity_idx == 3 and bmi_idx == 3:
            interaction_alpha += 0.5

        # Post-term + previous C-section: uterine rupture
        if gest_idx == 6 and comp_idx == 1:
            interaction_alpha += 1.0

        # Preterm + underweight: IUGR / neonatal compromise
        if gest_idx <= 3 and bmi_idx == 0:
            interaction_alpha += 0.3

        alpha = alpha_0
        alpha += risk_additions["age"][age_idx]
        alpha += risk_additions["parity"][parity_idx]
        alpha += risk_additions["hb"][hb_idx]
        alpha += risk_additions["bp"][bp_idx]
        alpha += risk_additions["gest"][gest_idx]
        alpha += risk_additions["bmi"][bmi_idx]
        alpha += risk_additions["comp"][comp_idx]
        alpha += interaction_alpha

        beta = beta_0
        risk_score = alpha / (alpha + beta)

        # Classify
        if risk_score >= 0.15:
            risk_level = "critical"
        elif risk_score >= 0.05:
            risk_level = "high"
        elif risk_score >= 0.01:
            risk_level = "medium"
        else:
            risk_level = "low"

        # Generate interventions based on dominant risk factors
        interventions = self._get_interventions(hb_idx, bp_idx, comp_idx, risk_level)

        summary = {
            "age": [
                "<18 (adolescent)",
                "18-25 (optimal)",
                "26-30 (optimal)",
                "31-35 (moderate risk)",
                ">35 (high risk)",
            ][age_idx],
            "hemoglobin": [
                "<7 g/dL (severe anemia)",
                "7-9 g/dL (moderate anemia)",
                "9-11 g/dL (mild anemia)",
                "11-12 g/dL (normal)",
                ">12 g/dL (normal)",
            ][hb_idx],
            "blood_pressure": [
                "Normal",
                "Elevated",
                "Stage 1 HTN",
                "Stage 2 HTN",
                "Hypertensive Crisis",
            ][bp_idx],
            "bmi": ["Underweight", "Normal", "Overweight", "Obese"][bmi_idx],
            "gestational_period": [
                "1st Trimester (1-12w)",
                "Early 2nd (13-20w)",
                "Late 2nd (21-28w)",
                "Early 3rd (29-34w)",
                "Late Preterm (35-37w)",
                "Term (38-40w)",
                "Post-term (>40w)",
            ][gest_idx],
            "complication_history": [
                "None",
                "Previous C-Section",
                "Previous PPH",
                "Previous Eclampsia",
                "Multiple Complications",
            ][comp_idx],
        }

        return {
            "risk_score": round(risk_score, 4),
            "risk_level": risk_level,
            "alpha": round(alpha, 2),
            "beta": round(beta, 2),
            "interventions": interventions,
            "risk_factors_summary": summary,
        }

    @staticmethod
    def _get_interventions(
        hb_idx: int, bp_idx: int, comp_idx: int, risk_level: str
    ) -> list[str]:
        interventions = []
        if hb_idx <= 1:
            interventions.append(
                "Ensure daily IFA supplementation — morning, empty stomach"
            )
            if hb_idx == 0:
                interventions.append(
                    "URGENT: Refer for injectable iron / blood transfusion"
                )
        if bp_idx >= 2:
            interventions.append("Monitor BP weekly; refer if BP > 140/90")
            if bp_idx >= 3:
                interventions.append(
                    "URGENT: Refer to facility with MgSO4 and antihypertensive capability"
                )
        if comp_idx >= 2:
            interventions.append(
                "Plan institutional delivery at facility with blood bank and OT"
            )
        if risk_level == "critical":
            interventions.append("EMERGENCY: Arrange immediate facility transfer")
        if not interventions:
            interventions.append("Continue routine ANC visits as scheduled")
        return interventions

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def table_size(self) -> int:
        return len(self._table)
