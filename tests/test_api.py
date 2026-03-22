"""Tests for FastAPI endpoints."""
import pytest
from fastapi.testclient import TestClient
from app.main import app, risk_engine, referral_engine, anemia_engine
from app.api.v1.routes import set_engines
from pathlib import Path

# Ensure engines are loaded for API tests
data_dir = Path(__file__).parent.parent / "data"
risk_path = data_dir / "risk_table.json"
facility_path = data_dir / "facility_graph.json"
hb_path = data_dir / "hb_trajectories.json"

if risk_path.exists() and not risk_engine.is_loaded:
    risk_engine.load(str(risk_path))
elif not risk_engine.is_loaded:
    risk_engine._loaded = True  # fallback mode

if facility_path.exists() and not referral_engine.is_loaded:
    referral_engine.load(str(facility_path))
elif not referral_engine.is_loaded:
    referral_engine._loaded = True

if hb_path.exists() and not anemia_engine.is_loaded:
    anemia_engine.load(str(hb_path))
elif not anemia_engine.is_loaded:
    anemia_engine._loaded = True

set_engines(risk_engine, referral_engine, anemia_engine)

client = TestClient(app)


class TestHealthCheck:
    def test_health_endpoint(self):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestRiskScoreEndpoint:
    def test_valid_request(self):
        response = client.post("/api/v1/risk-score", json={
            "age": 25, "parity": 1, "hemoglobin": 12.0,
            "bp_systolic": 115, "bp_diastolic": 75,
            "gestational_weeks": 20, "height_cm": 160, "weight_kg": 55,
            "complication_history": "none"
        })
        assert response.status_code == 200
        data = response.json()
        assert "risk_score" in data
        assert "risk_level" in data

    def test_invalid_age_rejected(self):
        response = client.post("/api/v1/risk-score", json={
            "age": 5, "parity": 1, "hemoglobin": 12.0,
            "bp_systolic": 115, "bp_diastolic": 75,
            "gestational_weeks": 20, "height_cm": 160, "weight_kg": 55,
            "complication_history": "none"
        })
        assert response.status_code == 422

    def test_invalid_bp_relationship(self):
        """Diastolic >= systolic should be rejected."""
        response = client.post("/api/v1/risk-score", json={
            "age": 25, "parity": 1, "hemoglobin": 12.0,
            "bp_systolic": 80, "bp_diastolic": 90,
            "gestational_weeks": 20, "height_cm": 160, "weight_kg": 55,
            "complication_history": "none"
        })
        assert response.status_code == 422


class TestAssessmentEndpoint:
    def test_full_assessment(self):
        response = client.post("/api/v1/assessment", json={
            "mother_name": "Sunita",
            "asha_id": "ASHA-001",
            "risk_factors": {
                "age": 26, "parity": 1, "hemoglobin": 8.5,
                "bp_systolic": 130, "bp_diastolic": 85,
                "gestational_weeks": 20, "height_cm": 157, "weight_kg": 55,
                "complication_history": "none"
            },
            "latitude": 27.57,
            "longitude": 80.68,
            "ifa_compliance": 0.6,
            "dietary_score": 0.5,
            "prev_anemia": False
        })
        assert response.status_code == 200
        data = response.json()
        assert data["mother_name"] == "Sunita"
        assert "risk" in data
        assert "assessment_id" in data
        assert "follow_up_date" in data


class TestSecurityHeaders:
    def test_security_headers_present(self):
        response = client.get("/api/v1/health")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"


class TestHomePage:
    def test_home_returns_html(self):
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
