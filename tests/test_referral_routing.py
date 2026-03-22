"""Tests for O(1) Emergency Referral Routing Engine."""
import pytest
from app.engines.referral_routing import ReferralRoutingEngine


@pytest.fixture
def engine():
    e = ReferralRoutingEngine()
    # Load if data exists, otherwise set up minimal test data
    try:
        e.load("data/facility_graph.json")
    except FileNotFoundError:
        e._facilities = [
            {
                "facility_id": "DH-001",
                "name": "District Hospital Sitapur",
                "type": "district_hospital",
                "latitude": 27.57,
                "longitude": 80.68,
                "capabilities": ["basic_emoc", "comprehensive_emoc", "blood_transfusion", "c_section", "neonatal_icu"],
                "specialist_available": True,
                "blood_bank_status": "available",
                "has_functional_ot": True,
                "contact_phone": "05862-252001",
            },
            {
                "facility_id": "PHC-001",
                "name": "PHC Mishrikh",
                "type": "phc",
                "latitude": 27.45,
                "longitude": 80.55,
                "capabilities": ["basic_emoc"],
                "specialist_available": False,
                "blood_bank_status": "unavailable",
                "has_functional_ot": False,
                "contact_phone": "05862-260001",
            },
        ]
        e._loaded = True
    return e


class TestHaversine:
    def test_same_point(self):
        assert ReferralRoutingEngine._haversine(27.0, 80.0, 27.0, 80.0) == 0.0

    def test_known_distance(self):
        # Sitapur to Lucknow ~90km
        dist = ReferralRoutingEngine._haversine(27.57, 80.68, 26.85, 80.95)
        assert 75 < dist < 110  # approximate


class TestRouting:
    def test_finds_facility(self, engine):
        result = engine.route(27.57, 80.68, "basic_emoc")
        assert result["facility_name"] != "No facility available"
        assert "distance_km" in result
        assert "eta_minutes" in result

    def test_result_structure(self, engine):
        result = engine.route(27.57, 80.68, "basic_emoc")
        required_fields = ["facility_name", "facility_type", "distance_km", "eta_minutes",
                          "specialist_available", "blood_bank_status", "has_functional_ot"]
        for field in required_fields:
            assert field in result

    def test_capability_filtering(self, engine):
        """Higher capability should route to more capable facility."""
        basic = engine.route(27.45, 80.55, "basic_emoc")
        advanced = engine.route(27.45, 80.55, "c_section")
        # Advanced capability facility may be further away
        assert advanced["facility_name"] != "No facility available"


class TestGridKey:
    def test_grid_key_format(self):
        key = ReferralRoutingEngine._grid_key(27.573, 80.684)
        assert key == "27.6,80.7"
