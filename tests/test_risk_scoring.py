"""Tests for O(1) Bayesian Maternal Risk Scoring Engine."""
import pytest
from app.engines.risk_scoring import RiskScoringEngine


@pytest.fixture
def engine():
    """Create a risk scoring engine instance (uses on-the-fly computation)."""
    e = RiskScoringEngine()
    e._loaded = True  # Enable fallback computation
    return e


class TestDiscretization:
    """Test that discretization functions correctly bucket values."""

    def test_age_buckets(self):
        assert RiskScoringEngine._discretize_age(15) == 0  # <18
        assert RiskScoringEngine._discretize_age(22) == 1  # 18-25
        assert RiskScoringEngine._discretize_age(28) == 2  # 26-30
        assert RiskScoringEngine._discretize_age(33) == 3  # 31-35
        assert RiskScoringEngine._discretize_age(40) == 4  # >35

    def test_parity_buckets(self):
        assert RiskScoringEngine._discretize_parity(0) == 0
        assert RiskScoringEngine._discretize_parity(2) == 1
        assert RiskScoringEngine._discretize_parity(4) == 2
        assert RiskScoringEngine._discretize_parity(6) == 3

    def test_hemoglobin_buckets(self):
        assert RiskScoringEngine._discretize_hb(5.0) == 0   # severe
        assert RiskScoringEngine._discretize_hb(8.0) == 1   # moderate
        assert RiskScoringEngine._discretize_hb(10.0) == 2  # mild
        assert RiskScoringEngine._discretize_hb(11.5) == 3  # normal
        assert RiskScoringEngine._discretize_hb(13.0) == 4  # normal+

    def test_bp_classification(self):
        assert RiskScoringEngine._discretize_bp(115, 75) == 0  # normal
        assert RiskScoringEngine._discretize_bp(125, 75) == 1  # elevated
        assert RiskScoringEngine._discretize_bp(135, 85) == 2  # stage1
        assert RiskScoringEngine._discretize_bp(145, 95) == 3  # stage2
        assert RiskScoringEngine._discretize_bp(185, 125) == 4 # crisis

    def test_bmi_computation(self):
        # Normal BMI: 55kg, 160cm = 21.5
        assert RiskScoringEngine._discretize_bmi(160, 55) == 1
        # Underweight: 40kg, 160cm = 15.6
        assert RiskScoringEngine._discretize_bmi(160, 40) == 0
        # Obese: 100kg, 160cm = 39.1
        assert RiskScoringEngine._discretize_bmi(160, 100) == 3


class TestRiskScoring:
    """Test risk scoring logic."""

    def test_low_risk_healthy_mother(self, engine):
        """Normal parameters should produce low or medium risk (conservative calibration)."""
        result = engine.score(
            age=25, parity=1, hemoglobin=12.5,
            bp_systolic=115, bp_diastolic=75,
            gestational_weeks=20, height_cm=160, weight_kg=55,
            complication_history="none"
        )
        assert result["risk_level"] in ("low", "medium")
        assert result["risk_score"] <= 0.02

    def test_critical_risk_severe_anemia_pph(self, engine):
        """Severe anemia + PPH history + hypertension should produce high or critical risk."""
        result = engine.score(
            age=35, parity=4, hemoglobin=5.5,
            bp_systolic=160, bp_diastolic=100,
            gestational_weeks=36, height_cm=155, weight_kg=70,
            complication_history="prev_pph"
        )
        assert result["risk_level"] in ("high", "critical")
        assert result["risk_score"] >= 0.05

    def test_medium_risk_moderate_anemia(self, engine):
        """Moderate anemia with normal other factors = medium risk."""
        result = engine.score(
            age=26, parity=1, hemoglobin=8.5,
            bp_systolic=130, bp_diastolic=85,
            gestational_weeks=20, height_cm=157, weight_kg=55,
            complication_history="none"
        )
        assert result["risk_level"] in ("medium", "high")
        assert result["risk_score"] >= 0.01

    def test_result_structure(self, engine):
        """Verify result contains all required fields."""
        result = engine.score(
            age=25, parity=0, hemoglobin=11.0,
            bp_systolic=120, bp_diastolic=80,
            gestational_weeks=16, height_cm=165, weight_kg=60,
            complication_history="none"
        )
        assert "risk_score" in result
        assert "risk_level" in result
        assert "alpha" in result
        assert "beta" in result
        assert "interventions" in result
        assert "risk_factors_summary" in result
        assert isinstance(result["interventions"], list)

    def test_hash_determinism(self):
        """Same inputs should always produce same hash."""
        h1 = RiskScoringEngine._compute_hash(1, 1, 2, 0, 3, 1, 0)
        h2 = RiskScoringEngine._compute_hash(1, 1, 2, 0, 3, 1, 0)
        assert h1 == h2

    def test_different_inputs_different_hashes(self):
        """Different inputs should produce different hashes."""
        h1 = RiskScoringEngine._compute_hash(1, 1, 2, 0, 3, 1, 0)
        h2 = RiskScoringEngine._compute_hash(1, 1, 2, 0, 3, 1, 1)
        assert h1 != h2

    def test_interventions_for_severe_anemia(self, engine):
        """Severe anemia should recommend urgent intervention."""
        result = engine.score(
            age=25, parity=1, hemoglobin=5.0,
            bp_systolic=110, bp_diastolic=70,
            gestational_weeks=28, height_cm=160, weight_kg=55,
            complication_history="none"
        )
        interventions = " ".join(result["interventions"]).lower()
        assert "iron" in interventions or "transfusion" in interventions or "urgent" in interventions


class TestSunitaCase:
    """Test the Sunita use case from the spec."""

    def test_sunita_risk_assessment(self, engine):
        """Sunita: 26, parity 1, Hb 8.5, BP 130/85, 20 weeks."""
        result = engine.score(
            age=26, parity=1, hemoglobin=8.5,
            bp_systolic=130, bp_diastolic=85,
            gestational_weeks=20, height_cm=157, weight_kg=55,
            complication_history="none"
        )
        # Should be medium-high risk per spec
        assert result["risk_level"] in ("medium", "high")
        assert result["risk_score"] >= 0.01
