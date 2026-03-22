"""API v1 routes for JananiSuraksha engines."""
import logging
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger("janani.routes")

from fastapi import APIRouter, HTTPException, Query

from app.persistence import AssessmentStore
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
    "Clinical Decision Support Tool — risk scores calibrated from NFHS-5 (724,115 women), "
    "WHO guidelines, Cochrane systematic reviews, and Lancet meta-analyses. "
    "Cross-validated against 5 independent data sources. Facility data from data.gov.in "
    "(Government of India). All assessments require human clinical review per India's "
    "Telemedicine Practice Guidelines 2020. Pending field validation via clinical trial."
)

# Engine instances will be set by main.py at startup
_risk_engine = None
_referral_engine = None
_anemia_engine = None
_real_facilities = None
_assessment_store = None


def set_engines(risk_engine, referral_engine, anemia_engine):
    global _risk_engine, _referral_engine, _anemia_engine
    _risk_engine = risk_engine
    _referral_engine = referral_engine
    _anemia_engine = anemia_engine


def set_real_facilities(finder: RealFacilityFinder):
    global _real_facilities
    _real_facilities = finder


def set_assessment_store(store: AssessmentStore):
    global _assessment_store
    _assessment_store = store


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

    # Step 1: Risk scoring (includes IFA, dietary, prev_anemia modifiers)
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
        ifa_compliance=request.ifa_compliance,
        dietary_score=request.dietary_score,
        prev_anemia=request.prev_anemia,
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

    # HUMAN-IN-THE-LOOP: All assessments require clinical confirmation
    # Per India's Telemedicine Practice Guidelines 2020 and DPDP Act 2023:
    # AI-generated risk scores are decision-SUPPORT, not autonomous diagnosis.
    human_review = {
        "required": True,
        "status": "PENDING_CLINICAL_REVIEW",
        "message": (
            "This AI-generated risk assessment REQUIRES review and confirmation "
            "by a qualified medical practitioner (ANM, MO, or specialist) before "
            "any clinical action is taken. The ASHA worker should present these "
            "findings to the sector ANM or PHC Medical Officer for confirmation."
        ),
        "review_level": (
            "Specialist (Gynecologist/Obstetrician)" if risk["risk_level"] == "critical"
            else "Medical Officer (PHC/CHC)" if risk["risk_level"] == "high"
            else "ANM (Auxiliary Nurse Midwife)" if risk["risk_level"] == "medium"
            else "Self-review by ASHA (routine)"
        ),
        "legal_basis": "India Telemedicine Practice Guidelines 2020, Section 3.7 — AI tools for decision support only",
        "override_allowed": True,
        "override_note": "Any qualified medical practitioner can override this AI assessment with documented clinical justification.",
    }

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

    response_dict = {
        "assessment_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "mother_name": request.mother_name,
        "risk": risk,
        "anemia": anemia,
        "referral": referral,
        "alerts": alerts,
        "follow_up_date": follow_up.strftime("%Y-%m-%d"),
        "recommendations": recommendations,
        "human_review": human_review,
        "disclaimer": DEMO_DISCLAIMER,
    }

    # Persist to SQLite store
    if _assessment_store:
        try:
            _assessment_store.save(response_dict)
        except Exception as e:
            logger.warning(f"Failed to persist assessment: {e}")

    return response_dict


@router.get("/dashboard-stats")
async def dashboard_stats():
    """Real-time dashboard statistics from actual assessments."""
    if not _assessment_store:
        return {"total_assessments": 0, "today_assessments": 0, "high_risk": 0, "critical_alerts": 0, "risk_distribution": {}}
    return _assessment_store.get_stats()


@router.get("/recent-assessments")
async def recent_assessments(limit: int = Query(20, ge=1, le=100)):
    """Recent assessment history."""
    if not _assessment_store:
        return {"assessments": []}
    assessments = _assessment_store.get_recent(limit)
    # Strip raw_result to keep response small
    for a in assessments:
        a.pop("raw_result", None)
    return {"assessments": assessments}


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


@router.post("/ambulance-dispatch")
async def ambulance_dispatch(
    mother_name: str = Query(...),
    latitude: float = Query(...),
    longitude: float = Query(...),
    risk_level: str = Query(...),
    complication: str = Query("obstetric_emergency"),
    facility_name: str = Query(""),
):
    """Ambulance dispatch endpoint — simulates 108/102 integration.

    In production, this would integrate with GVK EMRI 108 or state 102 services.
    Currently returns a dispatch confirmation with tracking info.
    """
    dispatch_id = f"AMB-{uuid.uuid4().hex[:8].upper()}"

    # Simulate dispatch based on risk level
    if risk_level == "critical":
        eta_minutes = 15
        priority = "P1 - CRITICAL"
        vehicle_type = "Advanced Life Support (ALS)"
    elif risk_level == "high":
        eta_minutes = 25
        priority = "P2 - HIGH"
        vehicle_type = "Basic Life Support (BLS)"
    else:
        eta_minutes = 45
        priority = "P3 - STANDARD"
        vehicle_type = "Patient Transport"

    return {
        "dispatch_id": dispatch_id,
        "status": "DISPATCHED",
        "timestamp": datetime.now().isoformat(),
        "priority": priority,
        "vehicle_type": vehicle_type,
        "eta_minutes": eta_minutes,
        "pickup_location": {"latitude": latitude, "longitude": longitude},
        "destination_facility": facility_name or "Nearest equipped facility",
        "mother_name": mother_name,
        "complication_type": complication,
        "emergency_numbers": {
            "national_ambulance": "108",
            "maternal_helpline": "102",
            "janani_express": "1800-180-1104",
        },
        "tracking_url": f"https://www.google.com/maps/dir/?api=1&origin={latitude},{longitude}&destination={facility_name or 'nearest+hospital'}&travelmode=driving",
        "note": "SIMULATION — In production, this dispatches a real ambulance via 108/GVK EMRI integration.",
        "disclaimer": DEMO_DISCLAIMER,
    }


@router.post("/send-alert")
async def send_alert(
    mother_name: str = Query(...),
    risk_level: str = Query(...),
    message: str = Query(""),
    alert_type: str = Query("family"),  # family, asha, anm, dho
):
    """Send alert via Telegram bot.

    Supports: family alerts, ASHA notifications, ANM escalation, DHO dashboard alerts.
    Uses Telegram Bot API (free, no SMS cost).
    """
    import httpx
    from app.config import get_settings
    settings = get_settings()

    # Build alert message
    emoji = {"critical": "\U0001f534", "high": "\U0001f7e0", "medium": "\U0001f7e1", "low": "\U0001f7e2"}.get(risk_level, "\u26aa")

    if not message:
        if risk_level == "critical":
            message = f"{emoji} EMERGENCY: {mother_name} is CRITICAL risk. Immediate facility transfer needed."
        elif risk_level == "high":
            message = f"{emoji} HIGH RISK: {mother_name} needs specialist referral within 48 hours."
        elif risk_level == "medium":
            message = f"{emoji} MEDIUM RISK: {mother_name} — ensure IFA compliance and schedule BP recheck in 2 weeks."
        else:
            message = f"{emoji} LOW RISK: {mother_name} — routine follow-up scheduled."

    alert_message = f"\U0001f3e5 *JananiSuraksha Alert*\n\n{message}\n\nType: {alert_type.upper()}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    # Send via Telegram if bot token is configured
    telegram_sent = False
    if settings.telegram_bot_token and settings.telegram_chat_id:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                    json={
                        "chat_id": settings.telegram_chat_id,
                        "text": alert_message,
                        "parse_mode": "Markdown",
                    }
                )
                telegram_sent = resp.status_code == 200
        except Exception as e:
            logger.warning(f"Telegram send failed: {e}")

    return {
        "status": "sent" if telegram_sent else "simulated",
        "channel": "telegram" if telegram_sent else "demo",
        "alert_type": alert_type,
        "mother_name": mother_name,
        "risk_level": risk_level,
        "message": alert_message,
        "telegram_delivered": telegram_sent,
        "note": "Configure JANANI_TELEGRAM_BOT_TOKEN and JANANI_TELEGRAM_CHAT_ID in .env to enable real Telegram alerts.",
    }
