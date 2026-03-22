"""API v1 routes for JananiSuraksha engines."""
from datetime import datetime, timedelta
import uuid

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (
    RiskFactors,
    RiskResult,
    ReferralRequest,
    ReferralResult,
    AnemiaInput,
    AnemiaResult,
    AssessmentRequest,
    AssessmentResult,
    HealthCheck,
)
from app.models.enums import (
    RiskLevel,
    CapabilityLevel,
    FacilityType,
    ComplicationHistory,
    InterventionUrgency,
    BloodBankStatus,
)
from app.engines.real_facilities import RealFacilityFinder

router = APIRouter(prefix="/api/v1", tags=["v1"])

DEMO_DISCLAIMER = (
    "DEMONSTRATION ONLY — NOT FOR CLINICAL USE. "
    "This system uses synthetic data and approximate risk models that have not been "
    "clinically validated. Do not use for real medical decisions. "
    "Always consult a qualified healthcare provider."
)

# Engine instances will be set by main.py at startup
_risk_engine = None
_referral_engine = None
_anemia_engine = None
_real_facilities = None


def set_engines(risk_engine, referral_engine, anemia_engine):
    global _risk_engine, _referral_engine, _anemia_engine
    _risk_engine = risk_engine
    _referral_engine = referral_engine
    _anemia_engine = anemia_engine


def set_real_facilities(finder: RealFacilityFinder):
    global _real_facilities
    _real_facilities = finder


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "engines_loaded": {
            "risk_scoring": _risk_engine.is_loaded if _risk_engine else False,
            "referral_routing": _referral_engine.is_loaded if _referral_engine else False,
            "anemia_prediction": _anemia_engine.is_loaded if _anemia_engine else False,
        }
    }


@router.post("/risk-score")
async def risk_score(factors: RiskFactors):
    """O(1) Bayesian maternal risk scoring."""
    if not _risk_engine:
        raise HTTPException(status_code=503, detail="Risk engine not loaded")

    result = _risk_engine.score(
        age=factors.age,
        parity=factors.parity,
        hemoglobin=factors.hemoglobin,
        bp_systolic=factors.bp_systolic,
        bp_diastolic=factors.bp_diastolic,
        gestational_weeks=factors.gestational_weeks,
        height_cm=factors.height_cm,
        weight_kg=factors.weight_kg,
        complication_history=factors.complication_history.value,
    )
    result["disclaimer"] = DEMO_DISCLAIMER
    return result


@router.post("/referral")
async def referral_route(request: ReferralRequest):
    """O(1) emergency referral routing."""
    if not _referral_engine:
        raise HTTPException(status_code=503, detail="Referral engine not loaded")

    result = _referral_engine.route(
        latitude=request.latitude,
        longitude=request.longitude,
        capability_required=request.capability_required.value,
        risk_level=request.risk_level.value,
    )
    result["disclaimer"] = DEMO_DISCLAIMER
    return result


@router.post("/anemia-predict")
async def anemia_predict(input_data: AnemiaInput):
    """O(1) anemia progression prediction."""
    if not _anemia_engine:
        raise HTTPException(status_code=503, detail="Anemia engine not loaded")

    result = _anemia_engine.predict(
        initial_hb=input_data.initial_hb,
        gestational_weeks=input_data.gestational_weeks,
        ifa_compliance=input_data.ifa_compliance,
        dietary_score=input_data.dietary_score,
        prev_anemia=input_data.prev_anemia,
    )
    result["disclaimer"] = DEMO_DISCLAIMER
    return result


@router.post("/assessment")
async def full_assessment(request: AssessmentRequest):
    """Complete ASHA worker assessment flow combining all three engines."""
    if not _risk_engine or not _referral_engine or not _anemia_engine:
        raise HTTPException(status_code=503, detail="Engines not loaded")

    # Step 1: Risk scoring
    risk = _risk_engine.score(
        age=request.risk_factors.age,
        parity=request.risk_factors.parity,
        hemoglobin=request.risk_factors.hemoglobin,
        bp_systolic=request.risk_factors.bp_systolic,
        bp_diastolic=request.risk_factors.bp_diastolic,
        gestational_weeks=request.risk_factors.gestational_weeks,
        height_cm=request.risk_factors.height_cm,
        weight_kg=request.risk_factors.weight_kg,
        complication_history=request.risk_factors.complication_history.value,
    )

    # Step 2: Anemia prediction (if Hb < 11)
    anemia = None
    if request.risk_factors.hemoglobin < 11.0:
        anemia = _anemia_engine.predict(
            initial_hb=request.risk_factors.hemoglobin,
            gestational_weeks=request.risk_factors.gestational_weeks,
            ifa_compliance=request.ifa_compliance,
            dietary_score=request.dietary_score,
            prev_anemia=request.prev_anemia,
        )

    # Step 3: Referral routing (if risk >= high)
    referral = None
    if risk["risk_level"] in ("high", "critical"):
        # Determine required capability from risk factors
        capability = "comprehensive_emoc"
        if request.risk_factors.hemoglobin < 7:
            capability = "blood_transfusion"
        if risk["risk_level"] == "critical":
            capability = "c_section"

        referral = _referral_engine.route(
            latitude=request.latitude,
            longitude=request.longitude,
            capability_required=capability,
            risk_level=risk["risk_level"],
        )

    # Step 4: Generate alerts
    alerts = []
    if risk["risk_level"] == "critical":
        alerts.append("EMERGENCY: Arrange immediate facility transfer")
    if risk["risk_level"] in ("high", "critical"):
        alerts.append("HIGH RISK pregnancy — refer to facility within 48 hours")
    if anemia and anemia["predicted_delivery_hb"] < 7.0:
        alerts.append("SEVERE ANEMIA RISK: Hb predicted to drop below 7 g/dL by delivery")
    if request.risk_factors.bp_systolic >= 140 or request.risk_factors.bp_diastolic >= 90:
        alerts.append("Elevated BP detected — monitor weekly, refer if persistent")

    # Step 5: Generate recommendations
    recommendations = risk.get("interventions", [])
    if anemia:
        if anemia["compliance_impact"]["with_90pct_compliance"] > anemia["predicted_delivery_hb"]:
            recommendations.append(
                f"With 90% IFA compliance, Hb can improve to "
                f"{anemia['compliance_impact']['with_90pct_compliance']} g/dL at delivery"
            )

    # Follow-up date
    if risk["risk_level"] == "critical":
        follow_up = datetime.now() + timedelta(days=3)
    elif risk["risk_level"] == "high":
        follow_up = datetime.now() + timedelta(days=7)
    elif risk["risk_level"] == "medium":
        follow_up = datetime.now() + timedelta(days=14)
    else:
        follow_up = datetime.now() + timedelta(days=30)

    return {
        "assessment_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "mother_name": request.mother_name,
        "risk": risk,
        "anemia": anemia,
        "referral": referral,
        "alerts": alerts,
        "follow_up_date": follow_up.strftime("%Y-%m-%d"),
        "recommendations": recommendations,
        "disclaimer": DEMO_DISCLAIMER,
    }


@router.get("/facilities")
async def list_facilities():
    """List all facilities for dashboard map."""
    if not _referral_engine:
        raise HTTPException(status_code=503, detail="Referral engine not loaded")
    return {"facilities": _referral_engine.get_all_facilities()}


@router.get("/nearby-facilities")
async def nearby_facilities(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    radius_km: float = Query(25.0, description="Search radius in km"),
    type: str = Query("hospital", description="Facility type filter"),
):
    """Find real nearby health facilities using data.gov.in + geocoding."""
    if not _real_facilities:
        raise HTTPException(status_code=503, detail="Real facilities finder not initialized")

    try:
        facilities = await _real_facilities.find_nearby(lat, lon, radius_km)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch facility data: {str(e)}")

    return {
        "facilities": facilities,
        "count": len(facilities),
        "search_center": {"lat": lat, "lon": lon},
        "radius_km": radius_km,
        "source": "data.gov.in National Hospital Directory",
        "disclaimer": DEMO_DISCLAIMER,
    }
