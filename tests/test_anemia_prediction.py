"""Tests for O(1) Anemia Progression Prediction Engine."""
import pytest
from app.engines.anemia_prediction import AnemiaPredictionEngine


@pytest.fixture
def engine():
    e = AnemiaPredictionEngine()
    e._loaded = True
    return e


class TestTrajectoryPrediction:
    def test_normal_hb_stays_safe(self, engine):
        """High initial Hb with good compliance should remain safe."""
        result = engine.predict(
            initial_hb=13.0, gestational_weeks=12,
            ifa_compliance=0.9, dietary_score=0.8, prev_anemia=False
        )
        assert result["predicted_delivery_hb"] >= 9.0
        assert result["risk_level"] in ("low", "medium")

    def test_low_hb_poor_compliance_is_critical(self, engine):
        """Low Hb + poor compliance should predict severe anemia."""
        result = engine.predict(
            initial_hb=7.5, gestational_weeks=16,
            ifa_compliance=0.1, dietary_score=0.2, prev_anemia=True
        )
        assert result["predicted_delivery_hb"] < 9.0
        assert result["risk_level"] in ("high", "critical")

    def test_compliance_impact_difference(self, engine):
        """With-compliance Hb should be higher than without."""
        result = engine.predict(
            initial_hb=9.0, gestational_weeks=20,
            ifa_compliance=0.5, dietary_score=0.5, prev_anemia=False
        )
        assert result["compliance_impact"]["with_90pct_compliance"] > result["compliance_impact"]["without_compliance"]

    def test_result_structure(self, engine):
        result = engine.predict(
            initial_hb=10.0, gestational_weeks=20,
            ifa_compliance=0.6, dietary_score=0.5, prev_anemia=False
        )
        assert "current_hb" in result
        assert "predicted_delivery_hb" in result
        assert "trajectory" in result
        assert "risk_level" in result
        assert "intervention_urgency" in result
        assert "compliance_impact" in result
        assert isinstance(result["trajectory"], list)

    def test_trajectory_weeks_are_sequential(self, engine):
        result = engine.predict(
            initial_hb=10.0, gestational_weeks=16,
            ifa_compliance=0.5, dietary_score=0.5, prev_anemia=False
        )
        weeks = [t["week"] for t in result["trajectory"]]
        assert weeks == sorted(weeks)
        assert weeks[0] == 16

    def test_sunita_case(self, engine):
        """Sunita: Hb 8.5 at 20 weeks, 60% IFA compliance."""
        result = engine.predict(
            initial_hb=8.5, gestational_weeks=20,
            ifa_compliance=0.6, dietary_score=0.5, prev_anemia=False
        )
        # Per spec: predicted 7.2 without full compliance, 9.8 with 90%
        assert result["predicted_delivery_hb"] < 10.0
        assert result["compliance_impact"]["with_90pct_compliance"] > result["predicted_delivery_hb"]


class TestFeatureDiscretization:
    def test_key_format(self):
        key = AnemiaPredictionEngine._discretize_features(
            initial_hb=10.0, gest_weeks=20,
            ifa_compliance=0.5, dietary_score=0.5, prev_anemia=False
        )
        assert isinstance(key, str)
        parts = key.split(":")
        assert len(parts) == 5

    def test_deterministic(self):
        k1 = AnemiaPredictionEngine._discretize_features(10.0, 20, 0.5, 0.5, False)
        k2 = AnemiaPredictionEngine._discretize_features(10.0, 20, 0.5, 0.5, False)
        assert k1 == k2
