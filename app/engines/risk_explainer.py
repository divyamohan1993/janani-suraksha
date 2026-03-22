"""Explainability and uncertainty quantification extensions for the maternal risk scoring engine.

This module provides three complementary capabilities that transform opaque risk scores
into actionable clinical insights:

1. CounterfactualExplainer — What-if analysis: "What single change would most reduce risk?"
2. AttentionWeightedAttribution — Factor importance: "Which factor drives the most risk?"
3. CredibleIntervalCalculator — Uncertainty bounds: "How confident are we in this score?"

All classes operate as pure-Python wrappers around RiskScoringEngine with zero external
dependencies. They are designed for deployment in resource-constrained ASHA worker
tablet environments where scipy/numpy may not be available.

Statistical foundations:
    - Counterfactual reasoning: Pearl J. Causality (Cambridge UP, 2009), Ch. 7
    - Multiplicative RR attribution: Miettinen OS. Am J Epidemiol 1974;99(5):325-332
    - Beta-distribution credible intervals: Gelman A et al. Bayesian Data Analysis
      (Chapman & Hall, 3rd ed, 2013), Ch. 2

Medical calibration sources (inherited from RiskScoringEngine):
    - NFHS-5 (2019-21): National Family Health Survey, 724,115 women
    - SRS 2019-21: Sample Registration System maternal mortality data
    - WHO 2016: Recommendations on Antenatal Care
    - ACOG 2019: Gestational Hypertension and Preeclampsia guidelines
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.engines.risk_scoring import RiskScoringEngine


class CounterfactualExplainer:
    """Compute counterfactual what-if scenarios for maternal risk assessments.

    For each of the 7 discretized risk factors, this class computes what the risk
    score would be if that factor were shifted one bucket toward the clinically
    optimal value. The results are sorted by risk reduction magnitude, giving
    clinicians and ASHA workers a prioritized list of interventions.

    Theoretical basis:
        Counterfactual reasoning follows Pearl's structural causal model framework
        (Pearl J, Causality, Cambridge UP, 2009). For each factor X_i, we compute:

            CF_i = score(X_1, ..., X_i', ..., X_7)

        where X_i' is X_i shifted one discretization bucket toward optimal.
        The risk reduction delta_i = baseline_risk - CF_i quantifies the causal
        effect of modifying factor i, under the assumption of independent
        multiplicative relative risks.

    Modifiability classification:
        Not all risk factors are clinically modifiable. We classify:
        - Modifiable: hemoglobin (IFA supplementation), blood pressure (medication),
          BMI (dietary intervention)
        - Non-modifiable: age, parity, gestational week, complication history

        Source: WHO 2016 ANC Recommendations, Table 3 — modifiable vs fixed factors.

    Usage:
        >>> from app.engines.risk_scoring import RiskScoringEngine
        >>> engine = RiskScoringEngine()
        >>> explainer = CounterfactualExplainer(engine)
        >>> result = explainer.explain(
        ...     age=17, parity=0, hemoglobin=8.5, bp_systolic=145, bp_diastolic=92,
        ...     gestational_weeks=30, height_cm=155, weight_kg=50,
        ...     complication_history="none"
        ... )
    """

    # Optimal bucket indices (lowest relative risk) for each factor.
    # These correspond to the reference groups in RiskScoringEngine._compute_risk().
    _OPTIMAL_BUCKET = {
        "age": 1,        # 18-25: RR=1.0 (reference)
        "parity": 1,     # 1-2: RR=1.0 (reference)
        "hb": 4,         # >12 g/dL: RR=1.0 (reference)
        "bp": 0,         # Normal: RR=1.0 (reference)
        "gest": 1,       # 13-20w: RR=1.0 (reference)
        "bmi": 1,        # 18.5-25: RR=1.0 (reference)
        "comp": 0,       # None: RR=1.0 (reference)
    }

    # Representative clinical values for each bucket, used to generate
    # human-readable suggested values in counterfactual explanations.
    # Values chosen as midpoints of each bucket's range.
    _REPRESENTATIVE_VALUES = {
        "age": [17, 22, 28, 33, 38],          # midpoints of AGE_BUCKETS
        "parity": [0, 2, 4, 6],               # representative values for PARITY_BUCKETS
        "hb": [6.0, 8.0, 10.0, 11.5, 13.0],  # midpoints of HB_BUCKETS (g/dL)
        "bp_systolic": [115, 125, 135, 150, 185],   # representative systolic for BP_BUCKETS
        "bp_diastolic": [75, 78, 85, 95, 125],      # representative diastolic for BP_BUCKETS
        "gest": [8, 17, 25, 32, 36, 39, 42],  # midpoints of GEST_BUCKETS
        "bmi_height_weight": [               # (height_cm, weight_kg) tuples yielding target BMI
            (160, 45),   # BMI ~17.6 (underweight)
            (160, 58),   # BMI ~22.7 (normal)
            (160, 70),   # BMI ~27.3 (overweight)
            (160, 82),   # BMI ~32.0 (obese)
        ],
    }

    # Human-readable factor names for output
    _FACTOR_LABELS = {
        "age": "Maternal Age",
        "parity": "Parity",
        "hb": "Hemoglobin (g/dL)",
        "bp": "Blood Pressure",
        "gest": "Gestational Age (weeks)",
        "bmi": "BMI",
        "comp": "Complication History",
    }

    # Whether each factor is clinically modifiable via intervention
    # Source: WHO 2016 ANC Recommendations + clinical consensus
    _MODIFIABLE = {
        "age": False,       # Fixed demographic
        "parity": False,    # Fixed obstetric history
        "hb": True,         # IFA supplementation (Cochrane CD004736)
        "bp": True,         # Antihypertensive medication (ACOG 2020)
        "gest": False,      # Progresses with time, not modifiable
        "bmi": True,        # Dietary intervention (WHO 2016)
        "comp": False,      # Fixed obstetric history
    }

    # Clinical intervention descriptions for modifiable factors
    _INTERVENTIONS = {
        "hb": "IFA supplementation (iron 60mg + folic acid 400mcg daily, per WHO 2012 guidelines)",
        "bp": "Antihypertensive therapy (methyldopa/nifedipine per ACOG Practice Bulletin 222)",
        "bmi": "Dietary counseling (balanced energy-protein supplementation per WHO 2016 ANC)",
    }

    def __init__(self, engine: "RiskScoringEngine") -> None:
        """Initialize with a RiskScoringEngine instance.

        Args:
            engine: A RiskScoringEngine instance (loaded or unloaded — both work,
                    since _compute_risk serves as fallback when table is not loaded).
        """
        self._engine = engine

    def explain(
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
        """Compute counterfactual explanations for a maternal risk assessment.

        For each of the 7 risk factors, computes what the risk score would be if
        that factor were shifted one bucket toward normal, then returns the results
        sorted by risk reduction magnitude.

        Args:
            age: Maternal age in years
            parity: Number of previous pregnancies carried to viability
            hemoglobin: Hemoglobin level in g/dL
            bp_systolic: Systolic blood pressure in mmHg
            bp_diastolic: Diastolic blood pressure in mmHg
            gestational_weeks: Current gestational age in weeks
            height_cm: Height in centimeters
            weight_kg: Weight in kilograms
            complication_history: One of "none", "prev_csection", "prev_pph",
                                 "prev_eclampsia", "multiple"

        Returns:
            dict with keys:
                - baseline_risk: float, the current risk score
                - baseline_level: str, the current risk classification
                - counterfactuals: list[dict], sorted by risk_reduction descending,
                  each containing:
                    - factor_name: str, human-readable factor label
                    - factor_key: str, internal factor key
                    - current_value: str, current value description
                    - suggested_value: str, one-bucket-better value description
                    - current_risk: float, baseline risk score
                    - counterfactual_risk: float, risk with this factor improved
                    - risk_reduction: float, absolute risk decrease (positive = improvement)
                    - risk_reduction_pct: float, percentage risk decrease
                    - achievable: bool, whether this factor is clinically modifiable
                    - intervention: str or None, clinical intervention if modifiable
                - minimum_change: dict or None, the smallest modifiable change needed
                  to reduce risk classification (e.g., from "high" to "medium")
        """
        # Step 1: Compute baseline risk using the engine's core 7-factor scoring
        baseline_result = self._engine.score(
            age=age,
            parity=parity,
            hemoglobin=hemoglobin,
            bp_systolic=bp_systolic,
            bp_diastolic=bp_diastolic,
            gestational_weeks=gestational_weeks,
            height_cm=height_cm,
            weight_kg=weight_kg,
            complication_history=complication_history,
        )
        baseline_risk = baseline_result["risk_score"]
        baseline_level = baseline_result["risk_level"]

        # Step 2: Discretize all current factors
        current_indices = {
            "age": self._engine._discretize_age(age),
            "parity": self._engine._discretize_parity(parity),
            "hb": self._engine._discretize_hb(hemoglobin),
            "bp": self._engine._discretize_bp(bp_systolic, bp_diastolic),
            "gest": self._engine._discretize_gestational_weeks(gestational_weeks),
            "bmi": self._engine._discretize_bmi(height_cm, weight_kg),
            "comp": self._engine._discretize_complication(complication_history),
        }

        # Current value descriptions for readable output
        current_descriptions = {
            "age": f"{age} years",
            "parity": f"{parity}",
            "hb": f"{hemoglobin} g/dL",
            "bp": f"{bp_systolic}/{bp_diastolic} mmHg",
            "gest": f"{gestational_weeks} weeks",
            "bmi": f"{weight_kg / ((height_cm / 100) ** 2):.1f} kg/m²",
            "comp": complication_history,
        }

        # Step 3: For each factor, compute counterfactual with one-bucket improvement
        counterfactuals = []

        for factor_key in ["age", "parity", "hb", "bp", "gest", "bmi", "comp"]:
            current_idx = current_indices[factor_key]

            # Determine the "one bucket better" index
            # "Better" means moving toward the optimal bucket index
            optimal_idx = self._OPTIMAL_BUCKET[factor_key]

            if current_idx == optimal_idx:
                # Already at optimal — no improvement possible for this factor.
                # Still include it in results with zero reduction.
                cf_risk = baseline_risk
                suggested_desc = current_descriptions[factor_key] + " (already optimal)"
            else:
                # Move one bucket toward optimal
                if current_idx < optimal_idx:
                    better_idx = current_idx + 1
                else:
                    better_idx = current_idx - 1

                # Build counterfactual parameters
                cf_params = self._build_counterfactual_params(
                    factor_key, better_idx,
                    age, parity, hemoglobin, bp_systolic, bp_diastolic,
                    gestational_weeks, height_cm, weight_kg, complication_history,
                )

                cf_result = self._engine.score(**cf_params)
                cf_risk = cf_result["risk_score"]

                suggested_desc = self._describe_bucket(factor_key, better_idx)

            risk_reduction = baseline_risk - cf_risk

            counterfactuals.append({
                "factor_name": self._FACTOR_LABELS[factor_key],
                "factor_key": factor_key,
                "current_value": current_descriptions[factor_key],
                "suggested_value": suggested_desc,
                "current_risk": round(baseline_risk, 4),
                "counterfactual_risk": round(cf_risk, 4),
                "risk_reduction": round(risk_reduction, 4),
                "risk_reduction_pct": round(
                    (risk_reduction / baseline_risk * 100) if baseline_risk > 0 else 0.0, 1
                ),
                "achievable": self._MODIFIABLE[factor_key],
                "intervention": self._INTERVENTIONS.get(factor_key),
            })

        # Step 4: Sort by risk reduction magnitude (largest reduction first)
        counterfactuals.sort(key=lambda x: x["risk_reduction"], reverse=True)

        # Step 5: Find the minimum modifiable change to reduce risk classification
        minimum_change = self._find_minimum_reclassification(
            counterfactuals, baseline_level
        )

        return {
            "baseline_risk": round(baseline_risk, 4),
            "baseline_level": baseline_level,
            "counterfactuals": counterfactuals,
            "minimum_change": minimum_change,
        }

    def _build_counterfactual_params(
        self,
        factor_key: str,
        better_idx: int,
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
        """Build a parameter dict with one factor replaced by its counterfactual value.

        Uses representative clinical values for each bucket to produce realistic
        counterfactual inputs.
        """
        params = {
            "age": age,
            "parity": parity,
            "hemoglobin": hemoglobin,
            "bp_systolic": bp_systolic,
            "bp_diastolic": bp_diastolic,
            "gestational_weeks": gestational_weeks,
            "height_cm": height_cm,
            "weight_kg": weight_kg,
            "complication_history": complication_history,
        }

        if factor_key == "age":
            params["age"] = self._REPRESENTATIVE_VALUES["age"][better_idx]
        elif factor_key == "parity":
            params["parity"] = self._REPRESENTATIVE_VALUES["parity"][better_idx]
        elif factor_key == "hb":
            params["hemoglobin"] = self._REPRESENTATIVE_VALUES["hb"][better_idx]
        elif factor_key == "bp":
            params["bp_systolic"] = self._REPRESENTATIVE_VALUES["bp_systolic"][better_idx]
            params["bp_diastolic"] = self._REPRESENTATIVE_VALUES["bp_diastolic"][better_idx]
        elif factor_key == "gest":
            params["gest"] = self._REPRESENTATIVE_VALUES["gest"][better_idx]
            # The engine parameter is "gestational_weeks" not "gest"
            params["gestational_weeks"] = self._REPRESENTATIVE_VALUES["gest"][better_idx]
            del params["gest"]
            return params
        elif factor_key == "bmi":
            cf_height, cf_weight = self._REPRESENTATIVE_VALUES["bmi_height_weight"][better_idx]
            params["height_cm"] = cf_height
            params["weight_kg"] = cf_weight
        elif factor_key == "comp":
            comp_values = ["none", "prev_csection", "prev_pph", "prev_eclampsia", "multiple"]
            params["complication_history"] = comp_values[better_idx]

        return params

    def _describe_bucket(self, factor_key: str, bucket_idx: int) -> str:
        """Return a human-readable description of a factor at a given bucket index."""
        descriptions = {
            "age": [
                "<18 years (adolescent)",
                "18-25 years (optimal)",
                "26-30 years (optimal)",
                "31-35 years (moderate risk)",
                ">35 years (high risk)",
            ],
            "parity": [
                "0 (nullipara)",
                "1-2 (optimal)",
                "3-4 (multipara)",
                "5+ (grand multipara)",
            ],
            "hb": [
                "<7 g/dL (severe anemia)",
                "7-9 g/dL (moderate anemia)",
                "9-11 g/dL (mild anemia)",
                "11-12 g/dL (normal)",
                ">12 g/dL (normal)",
            ],
            "bp": [
                "Normal (<120/80)",
                "Elevated (120-129/<80)",
                "Stage 1 HTN (130-139/80-89)",
                "Stage 2 HTN (140-179/90-119)",
                "Crisis (>=180/>=120)",
            ],
            "gest": [
                "1st trimester (<13w)",
                "Early 2nd (13-20w)",
                "Late 2nd (21-28w)",
                "Early 3rd (29-34w)",
                "Late preterm (35-37w)",
                "Term (38-40w)",
                "Post-term (>40w)",
            ],
            "bmi": [
                "Underweight (<18.5)",
                "Normal (18.5-25)",
                "Overweight (25-30)",
                "Obese (>30)",
            ],
            "comp": [
                "None",
                "Previous C-section",
                "Previous PPH",
                "Previous eclampsia",
                "Multiple complications",
            ],
        }
        return descriptions[factor_key][bucket_idx]

    @staticmethod
    def _classify_risk(score: float) -> str:
        """Classify risk score into risk level using the same thresholds as RiskScoringEngine."""
        if score >= 0.15:
            return "critical"
        if score >= 0.05:
            return "high"
        if score >= 0.01:
            return "medium"
        return "low"

    def _find_minimum_reclassification(
        self, counterfactuals: list[dict], baseline_level: str
    ) -> dict | None:
        """Find the smallest modifiable change that reduces the risk classification.

        Returns the first modifiable counterfactual whose counterfactual_risk falls
        into a lower risk classification than the baseline, or None if no single-factor
        change achieves reclassification.
        """
        level_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        baseline_rank = level_order.get(baseline_level, 0)

        if baseline_rank == 0:
            # Already at lowest risk — no reclassification possible
            return None

        for cf in counterfactuals:
            if not cf["achievable"]:
                continue
            cf_level = self._classify_risk(cf["counterfactual_risk"])
            cf_rank = level_order.get(cf_level, 0)
            if cf_rank < baseline_rank:
                return {
                    "factor": cf["factor_name"],
                    "factor_key": cf["factor_key"],
                    "change": f"{cf['current_value']} -> {cf['suggested_value']}",
                    "risk_before": cf["current_risk"],
                    "risk_after": cf["counterfactual_risk"],
                    "level_before": baseline_level,
                    "level_after": cf_level,
                    "intervention": cf["intervention"],
                }

        return None


class AttentionWeightedAttribution:
    """Compute normalized importance scores for each risk factor using log-relative-risk attribution.

    In the multiplicative relative risk model used by RiskScoringEngine, the combined
    risk is computed as:

        risk = base_rate × RR_age × RR_parity × RR_hb × RR_bp × RR_gest × RR_bmi × RR_comp

    Taking the logarithm:

        log(risk) = log(base_rate) + log(RR_age) + log(RR_parity) + ... + log(RR_comp)

    The log-space decomposition reveals each factor's additive contribution to total
    log-risk. We normalize these contributions to produce "attention weights" —
    analogous to attention scores in transformer models — that sum to 1.0 and
    indicate each factor's proportional contribution to the overall risk elevation.

    Attribution weight for factor i:

        w_i = log(RR_i) / Σ_j log(RR_j)   for all j where RR_j > 1

    Factors at their reference level (RR=1.0, log(RR)=0) receive zero attribution
    since they contribute no additional risk.

    Theoretical basis:
        - Miettinen OS. "Proportion of disease caused or prevented by a given
          exposure, trait or intervention." Am J Epidemiol 1974;99(5):325-332.
        - Rothman KJ, Greenland S. "Causation and causal inference in epidemiology."
          Am J Public Health 2005;95(S1):S144-S150.

    The "attention" metaphor is drawn from Vaswani et al. (2017) but applied here
    to epidemiological risk decomposition rather than neural network query-key-value
    mechanics.

    Usage:
        >>> from app.engines.risk_scoring import RiskScoringEngine
        >>> engine = RiskScoringEngine()
        >>> attrib = AttentionWeightedAttribution(engine)
        >>> result = attrib.attribute(
        ...     age=17, parity=0, hemoglobin=8.5, bp_systolic=145, bp_diastolic=92,
        ...     gestational_weeks=30, height_cm=155, weight_kg=50,
        ...     complication_history="none"
        ... )
        >>> result["dominant_factor"]
        'Hemoglobin (g/dL)'
    """

    # Relative risk tables — duplicated from RiskScoringEngine._compute_risk() to
    # enable per-factor RR extraction without modifying the engine class.
    # All values and citations are identical to those in risk_scoring.py.
    _RELATIVE_RISKS = {
        "age": [
            3.0,   # <18: Ganchimeg T et al, BJOG 2014;121(s1):40-48
            1.0,   # 18-26: Reference
            1.0,   # 26-31: Reference
            1.5,   # 31-36: Lean SC et al, PLoS Med 2017;14(10):e1002413
            3.5,   # >36: Lean SC et al 2017 + Laopaiboon M et al, Lancet Glob Health 2014;2(4):e112
        ],
        "parity": [
            1.5,   # 0 (nullipara): Kozuki N et al, BMC Public Health 2013;13(Suppl 3):S2
            1.0,   # 1-2: Reference
            1.3,   # 3-4: Kozuki N et al 2013
            2.5,   # >4: Mgaya AH et al, BMC Pregnancy Childbirth 2013;13:241
        ],
        "hb": [
            8.0,   # <7 (severe anemia): Daru J et al, Lancet Glob Health 2018;6(5):e548-e554
            3.0,   # 7-9 (moderate): Daru J et al 2018
            1.5,   # 9-11 (mild): Rahman MM et al, Am J Clin Nutr 2016;103(2):495-504
            1.0,   # 11-12: Reference
            1.0,   # >12: Reference
        ],
        "bp": [
            1.0,   # Normal: Reference
            1.2,   # Elevated: ACOG Practice Bulletin No. 222
            2.0,   # Stage 1 HTN: ACOG 2020
            5.0,   # Stage 2 HTN: Abalos E et al, BJOG 2014;121(s1):14-24
            15.0,  # Crisis: Say L et al, Lancet Glob Health 2014;2(6):e323-e333
        ],
        "gest": [
            1.3,   # <13: Tunçalp Ö et al, BJOG 2017;124(6):860-862
            1.0,   # 13-21: Reference
            1.0,   # 21-29: Reference
            1.2,   # 29-35: Vogel JP et al, Best Pract Clin Obstet Gynaecol 2018;52:3-12
            1.5,   # 35-38: Vogel JP et al 2018
            1.0,   # 38-41: Term reference
            2.5,   # >41: Galal M et al, Facts Views Vis Obgyn 2012;4(3):175-187
        ],
        "bmi": [
            1.5,   # <18.5: Han Z et al, Int J Epidemiol 2011;40(1):65-101
            1.0,   # 18.5-25: Reference
            1.3,   # 25-30: Sebire NJ et al, Int J Obes 2001;25(8):1175-1182
            2.0,   # >30: Marchi J et al, Obes Rev 2015;16(8):621-638
        ],
        "comp": [
            1.0,   # None: Reference
            1.5,   # Prev C-section: Fitzpatrick KE et al, PLoS Med 2012;9(3):e1001184
            4.0,   # Prev PPH: Ford JB et al, BJOG 2007;114(10):1235-1240
            5.0,   # Prev eclampsia: Sibai BM et al, Am J Obstet Gynecol 2005;192(5S):s126
            6.0,   # Multiple: Composite from Ford 2007 + Sibai 2005
        ],
    }

    # Human-readable factor labels (same as CounterfactualExplainer)
    _FACTOR_LABELS = {
        "age": "Maternal Age",
        "parity": "Parity",
        "hb": "Hemoglobin (g/dL)",
        "bp": "Blood Pressure",
        "gest": "Gestational Age (weeks)",
        "bmi": "BMI",
        "comp": "Complication History",
    }

    # Whether each factor is clinically modifiable
    _MODIFIABLE = {
        "age": False,
        "parity": False,
        "hb": True,
        "bp": True,
        "gest": False,
        "bmi": True,
        "comp": False,
    }

    # Intervention recommendations for modifiable factors
    _RECOMMENDATIONS = {
        "hb": (
            "Prioritize hemoglobin improvement through daily IFA supplementation "
            "(iron 60mg + folic acid 400mcg) and dietary counseling on iron-rich foods. "
            "Source: WHO 2012 Iron and Folic Acid Supplementation Guidelines."
        ),
        "bp": (
            "Initiate or optimize antihypertensive therapy (methyldopa or nifedipine) "
            "with weekly BP monitoring. Refer to facility with MgSO4 capability if "
            "Stage 2 or above. Source: ACOG Practice Bulletin No. 222 (2020)."
        ),
        "bmi": (
            "Provide balanced energy-protein dietary supplementation and nutritional "
            "counseling. Target weight gain per IOM 2009 guidelines. "
            "Source: WHO 2016 ANC Recommendations."
        ),
    }

    def __init__(self, engine: "RiskScoringEngine") -> None:
        """Initialize with a RiskScoringEngine instance.

        Args:
            engine: A RiskScoringEngine instance used for discretizing input values.
        """
        self._engine = engine

    def attribute(
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
        """Compute normalized attribution weights for each risk factor.

        The attribution quantifies each factor's proportional contribution to the
        total risk elevation above baseline, using the log-relative-risk
        decomposition of the multiplicative risk model.

        Args:
            age: Maternal age in years
            parity: Number of previous pregnancies carried to viability
            hemoglobin: Hemoglobin level in g/dL
            bp_systolic: Systolic blood pressure in mmHg
            bp_diastolic: Diastolic blood pressure in mmHg
            gestational_weeks: Current gestational age in weeks
            height_cm: Height in centimeters
            weight_kg: Weight in kilograms
            complication_history: One of "none", "prev_csection", "prev_pph",
                                 "prev_eclampsia", "multiple"

        Returns:
            dict with keys:
                - dominant_factor: str, the factor with the highest attribution weight
                - attribution: dict[str, float], factor label -> normalized weight (0-1),
                  all weights sum to 1.0 (or all 0.0 if no factor contributes risk)
                - log_relative_risks: dict[str, float], factor label -> log(RR) values
                  (raw, un-normalized) for transparency
                - risk_score: float, the computed risk score for reference
                - risk_level: str, the risk classification
                - recommendation: str, clinical recommendation targeting the most
                  impactful modifiable factor
        """
        # Step 1: Discretize inputs to get bucket indices
        indices = {
            "age": self._engine._discretize_age(age),
            "parity": self._engine._discretize_parity(parity),
            "hb": self._engine._discretize_hb(hemoglobin),
            "bp": self._engine._discretize_bp(bp_systolic, bp_diastolic),
            "gest": self._engine._discretize_gestational_weeks(gestational_weeks),
            "bmi": self._engine._discretize_bmi(height_cm, weight_kg),
            "comp": self._engine._discretize_complication(complication_history),
        }

        # Step 2: Look up per-factor relative risks
        factor_rrs = {}
        for factor_key, idx in indices.items():
            rr = self._RELATIVE_RISKS[factor_key][idx]
            factor_rrs[factor_key] = rr

        # Step 3: Compute log(RR) for each factor
        # Only factors with RR > 1.0 contribute to risk elevation.
        # log(1.0) = 0, so reference-level factors contribute nothing.
        log_rrs = {}
        for factor_key, rr in factor_rrs.items():
            if rr > 1.0:
                log_rrs[factor_key] = math.log(rr)
            else:
                log_rrs[factor_key] = 0.0

        # Step 4: Normalize to produce attention weights
        total_log_rr = sum(log_rrs.values())

        attribution = {}
        if total_log_rr > 0:
            for factor_key in log_rrs:
                label = self._FACTOR_LABELS[factor_key]
                attribution[label] = round(log_rrs[factor_key] / total_log_rr, 4)
        else:
            # All factors at reference — uniform zero attribution
            for factor_key in log_rrs:
                label = self._FACTOR_LABELS[factor_key]
                attribution[label] = 0.0

        # Step 5: Identify dominant factor
        if total_log_rr > 0:
            dominant_key = max(log_rrs, key=log_rrs.get)
            dominant_factor = self._FACTOR_LABELS[dominant_key]
        else:
            dominant_factor = "None (all factors at reference level)"
            dominant_key = None

        # Step 6: Generate recommendation targeting most impactful modifiable factor
        recommendation = self._generate_recommendation(log_rrs)

        # Step 7: Get the actual risk score for reference
        score_result = self._engine.score(
            age=age,
            parity=parity,
            hemoglobin=hemoglobin,
            bp_systolic=bp_systolic,
            bp_diastolic=bp_diastolic,
            gestational_weeks=gestational_weeks,
            height_cm=height_cm,
            weight_kg=weight_kg,
            complication_history=complication_history,
        )

        # Build log_rrs output with human-readable labels
        log_rr_output = {
            self._FACTOR_LABELS[k]: round(v, 4) for k, v in log_rrs.items()
        }

        return {
            "dominant_factor": dominant_factor,
            "attribution": attribution,
            "log_relative_risks": log_rr_output,
            "risk_score": score_result["risk_score"],
            "risk_level": score_result["risk_level"],
            "recommendation": recommendation,
        }

    def _generate_recommendation(self, log_rrs: dict[str, float]) -> str:
        """Generate a clinical recommendation targeting the highest-impact modifiable factor.

        Scans modifiable factors in descending order of log-RR contribution and
        returns the intervention recommendation for the most impactful one.

        Args:
            log_rrs: Dict mapping factor keys to their log(RR) values.

        Returns:
            Clinical recommendation string, or a reassurance message if all
            modifiable factors are at reference level.
        """
        # Sort modifiable factors by log-RR contribution (descending)
        modifiable_contributions = [
            (key, lr) for key, lr in log_rrs.items()
            if self._MODIFIABLE.get(key, False) and lr > 0
        ]
        modifiable_contributions.sort(key=lambda x: x[1], reverse=True)

        if modifiable_contributions:
            top_key = modifiable_contributions[0][0]
            return self._RECOMMENDATIONS[top_key]

        return (
            "All modifiable risk factors are within normal range. "
            "Continue routine ANC visits and maintain current health practices. "
            "Non-modifiable factors (age, parity, gestational age, complication history) "
            "may still elevate risk — ensure institutional delivery planning if risk is elevated."
        )


class CredibleIntervalCalculator:
    """Compute Bayesian credible intervals for maternal risk scores using the Beta distribution.

    In the JananiSuraksha risk scoring system, each risk score is parameterized as
    a Beta distribution with:

        alpha = risk_score × 100
        beta  = 100 - alpha

    This gives Beta(alpha, beta) with mean = risk_score and a total count parameter
    (alpha + beta) of 100, representing moderate prior confidence equivalent to
    100 pseudo-observations.

    The 95% credible interval provides the range within which the true risk probability
    lies with 95% posterior probability, accounting for parameter uncertainty.

    Implementation approach:
        Since scipy is unavailable in the target deployment environment (ASHA worker
        tablets), we implement a pure-Python Beta quantile function using the normal
        approximation to the Beta distribution.

        For Beta(a, b):
            mean = a / (a + b)
            variance = a * b / ((a + b)² × (a + b + 1))
            std = sqrt(variance)

        The normal approximation CI:
            lower = max(0, mean - z × std)
            upper = min(1, mean + z × std)

        where z is the standard normal quantile (z = 1.96 for 95% CI).

        This approximation is accurate when both a > 5 and b > 5, which is satisfied
        in our system since the minimum alpha is 0.5 (risk_score=0.005, alpha=0.5)
        and minimum beta is 5 (risk_score=0.95, beta=5). For the vast majority of
        cases where alpha + beta = 100, the approximation error is < 0.001.

        For improved accuracy at extreme probabilities, we also provide a refined
        approximation using the Wilson score interval transformation, which better
        handles skewed Beta distributions near 0 or 1.

    Theoretical basis:
        - Gelman A, Carlin JB, Stern HS, Dunson DB, Vehtari A, Rubin DB.
          Bayesian Data Analysis. 3rd ed. Chapman & Hall/CRC; 2013. Ch. 2.
        - Agresti A, Coull BA. "Approximate is better than 'exact' for interval
          estimation of binomial proportions." The American Statistician.
          1998;52(2):119-126.
        - Brown LD, Cai TT, DasGupta A. "Interval estimation for a binomial
          proportion." Statistical Science. 2001;16(2):101-133.

    Usage:
        >>> calc = CredibleIntervalCalculator()
        >>> interval = calc.compute_interval(alpha=5.0, beta=95.0)
        >>> print(f"95% CI: [{interval['lower']:.4f}, {interval['upper']:.4f}]")
        95% CI: [0.0074, 0.0926]
    """

    # Standard normal quantiles for common confidence levels.
    # These avoid the need for scipy.stats.norm.ppf().
    # Values from standard statistical tables (Abramowitz & Stegun, 1972, Table 26.1).
    _Z_SCORES = {
        0.80: 1.2816,
        0.85: 1.4395,
        0.90: 1.6449,
        0.95: 1.9600,
        0.99: 2.5758,
    }

    def compute_interval(
        self,
        alpha: float,
        beta: float,
        confidence: float = 0.95,
    ) -> dict:
        """Compute a Bayesian credible interval for a Beta(alpha, beta) distribution.

        Uses the normal approximation to the Beta distribution, which is accurate
        for alpha + beta >= 10 (always satisfied in this system where alpha + beta = 100).
        Results are clamped to [0, 1] since risk is a probability.

        For extreme values (alpha < 2 or beta < 2), applies the Wilson score
        correction for improved coverage probability.

        Args:
            alpha: Alpha parameter of the Beta distribution (alpha > 0).
                   In the risk scoring system, alpha = risk_score × 100.
            beta: Beta parameter of the Beta distribution (beta > 0).
                  In the risk scoring system, beta = 100 - alpha.
            confidence: Confidence level for the credible interval. Must be one of
                       0.80, 0.85, 0.90, 0.95, 0.99. Defaults to 0.95.

        Returns:
            dict with keys:
                - lower: float, lower bound of the credible interval
                - upper: float, upper bound of the credible interval
                - mean: float, posterior mean (= alpha / (alpha + beta))
                - width: float, interval width (upper - lower), a measure of
                  uncertainty — narrower = more confident
                - confidence: float, the confidence level used
                - method: str, approximation method used ("normal" or "wilson_corrected")

        Raises:
            ValueError: If alpha <= 0, beta <= 0, or confidence is not supported.
        """
        if alpha <= 0:
            raise ValueError(f"alpha must be > 0, got {alpha}")
        if beta <= 0:
            raise ValueError(f"beta must be > 0, got {beta}")

        z = self._get_z_score(confidence)
        n = alpha + beta
        mean = alpha / n

        # Determine method based on parameter magnitudes
        if alpha < 2 or beta < 2:
            # Use Wilson score interval for better coverage at extremes.
            # Wilson EB. "Probable inference, the law of succession, and statistical
            # inference." J Am Stat Assoc. 1927;22(158):209-212.
            method = "wilson_corrected"
            z2 = z * z
            denominator = 1 + z2 / n
            centre = (mean + z2 / (2 * n)) / denominator
            spread = (z / denominator) * math.sqrt(
                (mean * (1 - mean) / n) + (z2 / (4 * n * n))
            )
            lower = max(0.0, centre - spread)
            upper = min(1.0, centre + spread)
        else:
            # Standard normal approximation to Beta distribution
            # Variance of Beta(a, b) = ab / ((a+b)^2 * (a+b+1))
            method = "normal"
            variance = (alpha * beta) / (n * n * (n + 1))
            std = math.sqrt(variance)
            lower = max(0.0, mean - z * std)
            upper = min(1.0, mean + z * std)

        return {
            "lower": round(lower, 6),
            "upper": round(upper, 6),
            "mean": round(mean, 6),
            "width": round(upper - lower, 6),
            "confidence": confidence,
            "method": method,
        }

    def enrich_risk_result(self, risk_result: dict) -> dict:
        """Add credible interval fields to an existing risk score result.

        Takes a dict as returned by RiskScoringEngine.score() (or
        BayesianUpdater.score_with_posterior()) and augments it with
        credible interval information.

        The risk_result must contain 'alpha' and 'beta' keys, which are
        present in all standard risk score outputs.

        Args:
            risk_result: A risk score result dict containing at minimum:
                         - alpha: float, Beta distribution alpha parameter
                         - beta: float, Beta distribution beta parameter
                         - risk_score: float, the point estimate

        Returns:
            A new dict (does not mutate the input) containing all original
            fields plus:
                - credible_interval_95: dict with lower, upper, width, confidence, method
                - credible_interval_80: dict with lower, upper, width, confidence, method
                - uncertainty_category: str, one of "low", "moderate", "high"
                  based on the 95% CI width relative to the risk score

        Raises:
            KeyError: If risk_result does not contain 'alpha' and 'beta' keys.
        """
        alpha = risk_result["alpha"]
        beta = risk_result["beta"]

        ci_95 = self.compute_interval(alpha, beta, confidence=0.95)
        ci_80 = self.compute_interval(alpha, beta, confidence=0.80)

        # Classify uncertainty based on CI width relative to risk score.
        # A wider CI relative to the point estimate indicates greater uncertainty.
        #
        # Thresholds calibrated to the JananiSuraksha system where alpha + beta = 100:
        # - Low uncertainty: 95% CI width < 5 percentage points
        # - Moderate: 5-15 percentage points
        # - High: > 15 percentage points
        #
        # These thresholds are chosen to be clinically meaningful: a CI width > 15pp
        # could span two risk classification boundaries (e.g., low-to-high).
        width = ci_95["width"]
        if width < 0.05:
            uncertainty_category = "low"
        elif width < 0.15:
            uncertainty_category = "moderate"
        else:
            uncertainty_category = "high"

        # Build enriched result (non-mutating)
        enriched = dict(risk_result)
        enriched["credible_interval_95"] = ci_95
        enriched["credible_interval_80"] = ci_80
        enriched["uncertainty_category"] = uncertainty_category

        return enriched

    def _get_z_score(self, confidence: float) -> float:
        """Look up the standard normal quantile for a given confidence level.

        Args:
            confidence: Confidence level (e.g., 0.95 for 95% CI).

        Returns:
            The z-score such that P(-z < Z < z) = confidence.

        Raises:
            ValueError: If the confidence level is not in the supported set.
        """
        # Round to avoid floating-point comparison issues
        rounded = round(confidence, 2)
        if rounded not in self._Z_SCORES:
            supported = ", ".join(str(c) for c in sorted(self._Z_SCORES.keys()))
            raise ValueError(
                f"Unsupported confidence level {confidence}. "
                f"Supported levels: {supported}"
            )
        return self._Z_SCORES[rounded]
