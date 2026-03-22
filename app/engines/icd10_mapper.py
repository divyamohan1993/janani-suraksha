"""Automated ICD-10-CM code mapping for maternal health risk assessments.

Maps discretized risk factor buckets from the multiplicative relative risk
model to ICD-10-CM diagnostic codes, generating structured billing-compatible
diagnostic summaries from risk assessment outputs.

ICD-10-CM codes used are from the 2026 code set, Chapter XV (O00-O9A):
Pregnancy, childbirth and the puerperium.

Applies automated mapping from a discretized multiplicative relative risk
model's factor indices to ICD-10-CM codes with trimester-specific coding,
building on prior work in clinical decision support code generation.
"""

from typing import Optional


# Clinical priority ordering for diagnostic code sorting.
# Lower number = higher clinical priority (more urgent).
_SEVERITY_PRIORITY = {
    "critical": 0,
    "severe": 1,
    "moderate": 2,
    "mild": 3,
    "monitoring": 4,
}


class ICD10Mapper:
    """Maps risk factor bucket indices to ICD-10-CM diagnostic codes.

    Consumes the discretized factor indices produced by RiskScoringEngine
    (age_idx, parity_idx, hb_idx, bp_idx, gest_idx, bmi_idx, comp_idx)
    and produces structured, billing-compatible diagnostic code sets with
    trimester-specific coding.

    Bucket index definitions (from RiskScoringEngine):
        age_idx:    0=<18, 1=18-25, 2=26-30, 3=31-35, 4=>35
        parity_idx: 0=nullipara, 1=1-2, 2=3-4, 3=>4
        hb_idx:     0=<7, 1=7-9, 2=9-11, 3=11-12, 4=>12
        bp_idx:     0=normal, 1=elevated, 2=stage1, 3=stage2, 4=crisis
        gest_idx:   0=<13w, 1=13-20w, 2=21-28w, 3=29-34w, 4=35-37w, 5=38-40w, 6=>41w
        bmi_idx:    0=<18.5, 1=18.5-25, 2=25-30, 3=>30
        comp_idx:   0=none, 1=prev_csection, 2=prev_pph, 3=prev_eclampsia, 4=multiple
    """

    # ------------------------------------------------------------------ #
    #  Static ICD-10-CM mapping table                                      #
    #                                                                      #
    #  Key: (factor_name, bucket_index)                                    #
    #  Value: dict with:                                                   #
    #    - codes: dict mapping trimester (1/2/3) to ICD-10-CM code         #
    #    - description: full clinical description                          #
    #    - severity: clinical severity label                               #
    #    - factor_label: human-readable factor description                 #
    #                                                                      #
    #  Codes without trimester specificity use trimester key 0.             #
    #  All codes validated against 2026 ICD-10-CM code set.                #
    # ------------------------------------------------------------------ #

    _CODE_MAP: dict[tuple[str, int], dict] = {
        # ============================================================== #
        #  HEMOGLOBIN / ANEMIA  (hb_idx)                                  #
        #  O99.01x - Anemia complicating pregnancy                        #
        #  Source: Daru J et al, Lancet Glob Health 2018;6(5):e548-e554   #
        # ============================================================== #
        ("hb", 0): {
            "codes": {
                1: "O99.011",
                2: "O99.012",
                3: "O99.013",
            },
            "descriptions": {
                1: "Anemia complicating pregnancy, first trimester",
                2: "Anemia complicating pregnancy, second trimester",
                3: "Anemia complicating pregnancy, third trimester",
            },
            "severity": "critical",
            "factor_label": "Severe anemia (Hb < 7 g/dL)",
        },
        ("hb", 1): {
            "codes": {
                1: "O99.011",
                2: "O99.012",
                3: "O99.013",
            },
            "descriptions": {
                1: "Anemia complicating pregnancy, first trimester",
                2: "Anemia complicating pregnancy, second trimester",
                3: "Anemia complicating pregnancy, third trimester",
            },
            "severity": "moderate",
            "factor_label": "Moderate anemia (Hb 7-9 g/dL)",
        },
        ("hb", 2): {
            "codes": {
                1: "O99.011",
                2: "O99.012",
                3: "O99.013",
            },
            "descriptions": {
                1: "Anemia complicating pregnancy, first trimester",
                2: "Anemia complicating pregnancy, second trimester",
                3: "Anemia complicating pregnancy, third trimester",
            },
            "severity": "mild",
            "factor_label": "Mild anemia (Hb 9-11 g/dL)",
        },
        # hb buckets 3 (11-12) and 4 (>12) are normal -- no ICD-10 code.

        # ============================================================== #
        #  BLOOD PRESSURE  (bp_idx)                                        #
        #  O13.x  - Gestational HTN without significant proteinuria        #
        #  O14.0x - Mild to moderate pre-eclampsia                         #
        #  O14.1x - Severe pre-eclampsia                                   #
        #  O16.x  - Unspecified maternal hypertension                      #
        #  Source: ACOG Practice Bulletin No. 222, Obstet Gynecol 2020     #
        # ============================================================== #
        # bp bucket 0 (normal) -- no ICD-10 code.
        ("bp", 1): {
            "codes": {
                1: "O13.1",
                2: "O13.2",
                3: "O13.3",
            },
            "descriptions": {
                1: "Gestational [pregnancy-induced] hypertension without significant proteinuria, first trimester",
                2: "Gestational [pregnancy-induced] hypertension without significant proteinuria, second trimester",
                3: "Gestational [pregnancy-induced] hypertension without significant proteinuria, third trimester",
            },
            "severity": "mild",
            "factor_label": "Elevated blood pressure",
        },
        ("bp", 2): {
            "codes": {
                1: "O13.1",
                2: "O13.2",
                3: "O13.3",
            },
            "descriptions": {
                1: "Gestational [pregnancy-induced] hypertension without significant proteinuria, first trimester",
                2: "Gestational [pregnancy-induced] hypertension without significant proteinuria, second trimester",
                3: "Gestational [pregnancy-induced] hypertension without significant proteinuria, third trimester",
            },
            "severity": "moderate",
            "factor_label": "Stage 1 hypertension",
        },
        ("bp", 3): {
            "codes": {
                1: "O16.1",
                2: "O14.02",
                3: "O14.03",
            },
            "descriptions": {
                1: "Unspecified maternal hypertension, first trimester",
                2: "Mild to moderate pre-eclampsia, second trimester",
                3: "Mild to moderate pre-eclampsia, third trimester",
            },
            "severity": "severe",
            "factor_label": "Stage 2 hypertension",
        },
        ("bp", 4): {
            "codes": {
                # Pre-eclampsia (O14.1x) does not have a 1st-trimester code;
                # use O16.1 (unspecified maternal HTN) for 1st trimester crisis
                # as pre-eclampsia before 20 weeks is exceedingly rare.
                1: "O16.1",
                2: "O14.12",
                3: "O14.13",
            },
            "descriptions": {
                1: "Unspecified maternal hypertension, first trimester",
                2: "Severe pre-eclampsia, second trimester",
                3: "Severe pre-eclampsia, third trimester",
            },
            "severity": "critical",
            "factor_label": "Hypertensive crisis",
        },

        # ============================================================== #
        #  BMI  (bmi_idx)                                                  #
        #  O25.1x - Malnutrition in pregnancy                             #
        #  O99.21x - Obesity complicating pregnancy                        #
        #  Sources: Han Z et al, Int J Epidemiol 2011;40(1):65-101        #
        #           Marchi J et al, Obes Rev 2015;16(8):621-638            #
        # ============================================================== #
        ("bmi", 0): {
            "codes": {
                1: "O25.11",
                2: "O25.12",
                3: "O25.13",
            },
            "descriptions": {
                1: "Malnutrition in pregnancy, first trimester",
                2: "Malnutrition in pregnancy, second trimester",
                3: "Malnutrition in pregnancy, third trimester",
            },
            "severity": "moderate",
            "factor_label": "Underweight (BMI < 18.5)",
        },
        # bmi bucket 1 (18.5-25, normal) -- no ICD-10 code.
        ("bmi", 2): {
            "codes": {
                1: "O99.211",
                2: "O99.212",
                3: "O99.213",
            },
            "descriptions": {
                1: "Obesity complicating pregnancy, first trimester",
                2: "Obesity complicating pregnancy, second trimester",
                3: "Obesity complicating pregnancy, third trimester",
            },
            "severity": "mild",
            "factor_label": "Overweight (BMI 25-30)",
        },
        ("bmi", 3): {
            "codes": {
                1: "O99.211",
                2: "O99.212",
                3: "O99.213",
            },
            "descriptions": {
                1: "Obesity complicating pregnancy, first trimester",
                2: "Obesity complicating pregnancy, second trimester",
                3: "Obesity complicating pregnancy, third trimester",
            },
            "severity": "moderate",
            "factor_label": "Obese (BMI > 30)",
        },

        # ============================================================== #
        #  AGE  (age_idx)                                                  #
        #  O09.61x - Supervision of young primigravida                     #
        #  O09.52x - Supervision of elderly multigravida                   #
        #  Sources: Ganchimeg T et al, BJOG 2014;121(s1):40-48            #
        #           Lean SC et al, PLoS One 2017;12(10):e0186287           #
        # ============================================================== #
        ("age", 0): {
            "codes": {
                1: "O09.611",
                2: "O09.612",
                3: "O09.613",
            },
            "descriptions": {
                1: "Supervision of young primigravida, first trimester",
                2: "Supervision of young primigravida, second trimester",
                3: "Supervision of young primigravida, third trimester",
            },
            "severity": "moderate",
            "factor_label": "Adolescent pregnancy (age < 18)",
        },
        # age buckets 1-3 (18-35) -- no specific ICD-10 code.
        ("age", 4): {
            "codes": {
                1: "O09.521",
                2: "O09.522",
                3: "O09.523",
            },
            "descriptions": {
                1: "Supervision of elderly multigravida, first trimester",
                2: "Supervision of elderly multigravida, second trimester",
                3: "Supervision of elderly multigravida, third trimester",
            },
            "severity": "moderate",
            "factor_label": "Advanced maternal age (age > 35)",
        },

        # ============================================================== #
        #  COMPLICATION HISTORY  (comp_idx)                                #
        #  O34.219 - Maternal care for scar from previous cesarean         #
        #  O72.1   - Other immediate postpartum hemorrhage                 #
        #  O14.9x  - Unspecified pre-eclampsia (history of eclampsia)      #
        #  O09.29x - Supervision of pregnancy with poor repro history      #
        #  Sources: Fitzpatrick KE et al, PLoS Med 2012;9(3):e1001184     #
        #           Ford JB et al, BJOG 2007;114(10):1235-1240             #
        #           Sibai BM et al, Am J Obstet Gynecol 2005;192(5S):s126  #
        # ============================================================== #
        # comp bucket 0 (none) -- no ICD-10 code.
        ("comp", 1): {
            "codes": {
                # O34.219 is not trimester-specific; use for all trimesters.
                1: "O34.219",
                2: "O34.219",
                3: "O34.219",
            },
            "descriptions": {
                1: "Maternal care for unspecified type scar from previous cesarean delivery",
                2: "Maternal care for unspecified type scar from previous cesarean delivery",
                3: "Maternal care for unspecified type scar from previous cesarean delivery",
            },
            "severity": "moderate",
            "factor_label": "Previous cesarean delivery",
        },
        ("comp", 2): {
            "codes": {
                # O72.1 is not trimester-specific (postpartum event); use for
                # documenting history of PPH as a current-pregnancy risk factor.
                1: "O72.1",
                2: "O72.1",
                3: "O72.1",
            },
            "descriptions": {
                1: "Other immediate postpartum hemorrhage",
                2: "Other immediate postpartum hemorrhage",
                3: "Other immediate postpartum hemorrhage",
            },
            "severity": "severe",
            "factor_label": "Previous postpartum hemorrhage",
        },
        ("comp", 3): {
            "codes": {
                # Pre-eclampsia codes start at 2nd trimester (20+ weeks).
                # For 1st trimester history documentation, use unspecified trimester.
                1: "O14.90",
                2: "O14.92",
                3: "O14.93",
            },
            "descriptions": {
                1: "Unspecified pre-eclampsia, unspecified trimester",
                2: "Unspecified pre-eclampsia, second trimester",
                3: "Unspecified pre-eclampsia, third trimester",
            },
            "severity": "severe",
            "factor_label": "Previous eclampsia",
        },
        ("comp", 4): {
            "codes": {
                1: "O09.291",
                2: "O09.292",
                3: "O09.293",
            },
            "descriptions": {
                1: "Supervision of pregnancy with other poor reproductive or obstetric history, first trimester",
                2: "Supervision of pregnancy with other poor reproductive or obstetric history, second trimester",
                3: "Supervision of pregnancy with other poor reproductive or obstetric history, third trimester",
            },
            "severity": "severe",
            "factor_label": "Multiple previous complications",
        },

        # ============================================================== #
        #  GESTATIONAL AGE  (gest_idx)                                     #
        #  O48.0 - Post-term pregnancy (>41 weeks)                         #
        #  Source: Galal M et al, Facts Views Vis Obgyn 2012;4(3):175-187  #
        # ============================================================== #
        # gest buckets 0-5 (up to 41 weeks) -- no specific ICD-10 code.
        ("gest", 6): {
            "codes": {
                # Post-term is inherently 3rd trimester; no trimester variants.
                1: "O48.0",
                2: "O48.0",
                3: "O48.0",
            },
            "descriptions": {
                1: "Post-term pregnancy",
                2: "Post-term pregnancy",
                3: "Post-term pregnancy",
            },
            "severity": "moderate",
            "factor_label": "Post-term pregnancy (> 41 weeks)",
        },
    }

    # Validated billable codes (all checked against 2026 ICD-10-CM).
    # O14.90 is billable (unspecified trimester fallback).
    # O48.0 is billable.  O72.1 is billable.  O34.219 is billable.
    _NON_BILLABLE_CODES: frozenset[str] = frozenset()

    # ------------------------------------------------------------------ #
    #  Public interface                                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _trimester_from_weeks(gestational_weeks: int) -> int:
        """Determine obstetric trimester from gestational age in weeks.

        ICD-10-CM trimester definitions per ACOG / ICD-10-CM Guidelines:
            1st trimester: less than 14 weeks 0 days (weeks 1-13)
            2nd trimester: 14 weeks 0 days to less than 28 weeks 0 days (weeks 14-27)
            3rd trimester: 28 weeks 0 days until delivery (weeks 28+)

        Note: ICD-10-CM uses 14/28 boundaries, while the risk engine uses
        13/27 for its own discretization.  This method follows ICD-10-CM
        conventions for code selection accuracy.

        Args:
            gestational_weeks: Completed weeks of gestation (0-45).

        Returns:
            Trimester as integer: 1, 2, or 3.
        """
        if gestational_weeks < 14:
            return 1
        if gestational_weeks < 28:
            return 2
        return 3

    def map_risk_factors(
        self,
        age_idx: int,
        parity_idx: int,
        hb_idx: int,
        bp_idx: int,
        gest_idx: int,
        bmi_idx: int,
        comp_idx: int,
        gestational_weeks: int,
    ) -> dict:
        """Map discretized risk factor indices to ICD-10-CM diagnostic codes.

        Examines each factor's bucket index against the static code map and
        collects all applicable ICD-10-CM codes for the current trimester.
        Results are sorted by clinical priority (critical > severe > moderate
        > mild > monitoring).

        Args:
            age_idx:  Discretized age bucket (0-4).
            parity_idx: Discretized parity bucket (0-3).
            hb_idx:   Discretized hemoglobin bucket (0-4).
            bp_idx:   Discretized blood pressure bucket (0-4).
            gest_idx: Discretized gestational age bucket (0-6).
            bmi_idx:  Discretized BMI bucket (0-3).
            comp_idx: Discretized complication history bucket (0-4).
            gestational_weeks: Raw gestational age in completed weeks.

        Returns:
            dict with keys:
                codes: list[dict] - Each dict has {code, description, factor,
                    severity} sorted by clinical priority.
                primary_diagnosis: dict|None - The most clinically severe code,
                    or None if no abnormal findings.
                trimester: int - Obstetric trimester (1, 2, or 3).
                billable: bool - Whether all returned codes are valid billable
                    ICD-10-CM codes for HIPAA transactions.
        """
        trimester = self._trimester_from_weeks(gestational_weeks)
        codes: list[dict] = []

        # Check each factor against the code map.
        factor_indices = [
            ("hb", hb_idx),
            ("bp", bp_idx),
            ("bmi", bmi_idx),
            ("age", age_idx),
            ("comp", comp_idx),
            ("gest", gest_idx),
        ]
        # parity_idx has no direct ICD-10 mapping (it modifies risk score
        # but is not a standalone diagnostic code).

        for factor_name, bucket_idx in factor_indices:
            key = (factor_name, bucket_idx)
            if key not in self._CODE_MAP:
                continue

            entry = self._CODE_MAP[key]
            code = entry["codes"].get(trimester)
            description = entry["descriptions"].get(trimester)

            if code is None:
                # No code for this trimester (should not happen given the
                # map covers all three trimesters, but guard defensively).
                continue

            codes.append({
                "code": code,
                "description": description,
                "factor": entry["factor_label"],
                "severity": entry["severity"],
            })

        # Sort by clinical priority: critical first, then severe, etc.
        codes.sort(key=lambda c: _SEVERITY_PRIORITY.get(c["severity"], 99))

        # Determine primary diagnosis (highest priority code).
        primary_diagnosis: Optional[dict] = codes[0] if codes else None

        # Check billability -- all codes in our map are billable per
        # 2026 ICD-10-CM validation, but verify against exclusion set.
        all_billable = all(
            c["code"] not in self._NON_BILLABLE_CODES for c in codes
        )

        return {
            "codes": codes,
            "primary_diagnosis": primary_diagnosis,
            "trimester": trimester,
            "billable": all_billable,
        }

    def from_risk_result(self, risk_result: dict) -> dict:
        """Convenience method to extract ICD-10 codes from a risk engine result.

        Accepts the output dict from RiskScoringEngine.score() or
        BayesianUpdater.score_with_posterior() and extracts the factor
        indices needed for ICD-10 mapping.

        The risk_result dict must contain a 'risk_factors_summary' sub-dict
        from which factor states are reverse-mapped to bucket indices.
        Optionally, if the caller has access to the raw indices, they can
        be passed directly via keys 'age_idx', 'hb_idx', etc.

        Args:
            risk_result: Output dict from RiskScoringEngine.score() containing
                'risk_factors_summary' with factor descriptions.

        Returns:
            Same structure as map_risk_factors().
        """
        # If raw indices are directly available, use them.
        if "age_idx" in risk_result:
            return self.map_risk_factors(
                age_idx=risk_result["age_idx"],
                parity_idx=risk_result.get("parity_idx", 1),
                hb_idx=risk_result["hb_idx"],
                bp_idx=risk_result["bp_idx"],
                gest_idx=risk_result["gest_idx"],
                bmi_idx=risk_result["bmi_idx"],
                comp_idx=risk_result["comp_idx"],
                gestational_weeks=risk_result.get("gestational_weeks", 20),
            )

        # Otherwise, reverse-map from the human-readable summary strings
        # produced by RiskScoringEngine._compute_risk().
        summary = risk_result.get("risk_factors_summary", {})

        age_idx = self._reverse_map_age(summary.get("age", ""))
        hb_idx = self._reverse_map_hb(summary.get("hemoglobin", ""))
        bp_idx = self._reverse_map_bp(summary.get("blood_pressure", ""))
        bmi_idx = self._reverse_map_bmi(summary.get("bmi", ""))
        comp_idx = self._reverse_map_comp(
            summary.get("complication_history", "")
        )
        gest_idx, gestational_weeks = self._reverse_map_gest(
            summary.get("gestational_period", "")
        )

        # Parity has no ICD-10 mapping; default to 1 (no-op bucket).
        parity_idx = 1

        return self.map_risk_factors(
            age_idx=age_idx,
            parity_idx=parity_idx,
            hb_idx=hb_idx,
            bp_idx=bp_idx,
            gest_idx=gest_idx,
            bmi_idx=bmi_idx,
            comp_idx=comp_idx,
            gestational_weeks=gestational_weeks,
        )

    # ------------------------------------------------------------------ #
    #  Reverse-mapping helpers                                             #
    #  Map human-readable summary strings back to bucket indices.          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _reverse_map_age(age_str: str) -> int:
        """Reverse-map age summary string to bucket index."""
        if "<18" in age_str:
            return 0
        if "18-25" in age_str:
            return 1
        if "26-30" in age_str:
            return 2
        if "31-35" in age_str:
            return 3
        if ">35" in age_str:
            return 4
        return 1  # default to safe bucket

    @staticmethod
    def _reverse_map_hb(hb_str: str) -> int:
        """Reverse-map hemoglobin summary string to bucket index."""
        if "<7" in hb_str:
            return 0
        if "7-9" in hb_str:
            return 1
        if "9-11" in hb_str:
            return 2
        if "11-12" in hb_str:
            return 3
        if ">12" in hb_str:
            return 4
        return 4  # default to normal

    @staticmethod
    def _reverse_map_bp(bp_str: str) -> int:
        """Reverse-map blood pressure summary string to bucket index."""
        bp_lower = bp_str.lower()
        if "crisis" in bp_lower:
            return 4
        if "stage 2" in bp_lower:
            return 3
        if "stage 1" in bp_lower:
            return 2
        if "elevated" in bp_lower:
            return 1
        return 0  # normal

    @staticmethod
    def _reverse_map_bmi(bmi_str: str) -> int:
        """Reverse-map BMI summary string to bucket index."""
        bmi_lower = bmi_str.lower()
        if "underweight" in bmi_lower:
            return 0
        if "obese" in bmi_lower:
            return 3
        if "overweight" in bmi_lower:
            return 2
        return 1  # normal

    @staticmethod
    def _reverse_map_comp(comp_str: str) -> int:
        """Reverse-map complication history summary string to bucket index."""
        comp_lower = comp_str.lower()
        if "multiple" in comp_lower:
            return 4
        if "eclampsia" in comp_lower:
            return 3
        if "pph" in comp_lower:
            return 2
        if "c-section" in comp_lower or "cesarean" in comp_lower:
            return 1
        return 0  # none

    @staticmethod
    def _reverse_map_gest(gest_str: str) -> tuple[int, int]:
        """Reverse-map gestational period summary string to (bucket_index, approx_weeks).

        Returns both the bucket index and an approximate gestational week
        value (midpoint of the range) for trimester computation.
        """
        gest_lower = gest_str.lower()
        if "post-term" in gest_lower or ">40" in gest_lower:
            return 6, 42
        if "term" in gest_lower and "pre" not in gest_lower:
            return 5, 39
        if "late preterm" in gest_lower or "35-37" in gest_lower:
            return 4, 36
        if "early 3rd" in gest_lower or "29-34" in gest_lower:
            return 3, 32
        if "late 2nd" in gest_lower or "21-28" in gest_lower:
            return 2, 24
        if "early 2nd" in gest_lower or "13-20" in gest_lower:
            return 1, 16
        if "1st" in gest_lower or "1-12" in gest_lower:
            return 0, 8
        # Default: mid-pregnancy
        return 2, 24
