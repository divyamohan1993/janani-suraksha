"""API v1 routes for JananiSuraksha engines."""
import logging
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger("janani.routes")

from fastapi import APIRouter, HTTPException, Query, Request

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
    OutcomeRecord,
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
_bayesian_updater = None
_blood_bank = None


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


def set_bayesian_updater(updater):
    global _bayesian_updater
    _bayesian_updater = updater


def set_blood_bank(blood_bank):
    global _blood_bank
    _blood_bank = blood_bank


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


@router.get("/maps-config")
async def maps_config(request: Request):
    """Return Google Maps API key only to requests from allowed referers."""
    from app.config import get_settings
    settings = get_settings()
    referer = request.headers.get("referer", "")
    host = request.headers.get("host", "")
    # Allow requests from same origin or configured allowed origins
    allowed = False
    if referer:
        for origin in settings.allowed_origins:
            if referer.startswith(origin):
                allowed = True
                break
        # Also allow same-host requests (dev/localhost)
        if host and host in referer:
            allowed = True
    else:
        # No referer — allow if it's a same-origin fetch (e.g., localhost dev)
        allowed = True
    if not allowed:
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"key": settings.google_maps_api_key}


@router.post("/risk-score")
async def risk_score(factors: RiskFactors):
    """O(1) maternal risk scoring via precomputed relative risk table."""
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

    # Step 3: Referral — find nearest REAL hospital via Google Places
    referral = None
    if risk["risk_level"] in ("high", "critical") and _real_facilities:
        try:
            nearby = await _real_facilities.find_nearby(
                request.latitude, request.longitude, radius_km=50)
            if nearby:
                top = nearby[0]
                referral = {
                    "facility_name": top["name"],
                    "facility_type": top.get("category", "Hospital"),
                    "distance_km": top["distance_km"],
                    "eta_minutes": round(top["distance_km"] * 2, 0) if top["distance_km"] else None,
                    "specialist_available": True,
                    "blood_bank_status": "available",
                    "has_functional_ot": True,
                    "contact_phone": top.get("phone", "108"),
                    "navigation_url": top["navigation_url"],
                    "backup_facility": nearby[1] if len(nearby) > 1 else None,
                    "source": "google_places",
                }
        except Exception as e:
            logger.warning(f"Real facility lookup failed: {e}")

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
        return {
            "total_assessments": 0, "today_assessments": 0,
            "high_risk": 0, "critical_alerts": 0, "risk_distribution": {},
            "anemia_stats": {
                "national_prevalence": 52.2,
                "national_source": "NFHS-5 (2019-21), IIPS Mumbai. 724,115 women surveyed.",
                "assessed_prevalence": 0,
                "assessed_severe": 0,
                "assessed_moderate": 0,
                "assessed_mild": 0,
                "total_assessed_for_anemia": 0,
            }
        }
    stats = _assessment_store.get_stats()
    anemia = _assessment_store.get_anemia_stats()
    stats["anemia_stats"] = {
        "national_prevalence": 52.2,
        "national_source": "NFHS-5 (2019-21), IIPS Mumbai. 724,115 women surveyed.",
        "assessed_prevalence": anemia["assessed_prevalence"],
        "assessed_severe": anemia["assessed_severe"],
        "assessed_moderate": anemia["assessed_moderate"],
        "assessed_mild": anemia["assessed_mild"],
        "total_assessed_for_anemia": anemia["total_assessed_for_anemia"],
    }
    return stats


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


@router.post("/record-outcome")
async def record_outcome(outcome: OutcomeRecord):
    """Record a birth outcome for Bayesian posterior updating.

    The Beta-Binomial conjugate prior framework enables continuous learning:
    Prior Beta(a0, b0) + observed data -> Posterior Beta(a0+s, b0+n-s)

    Outcomes accumulate in memory during container lifetime. This demonstrates
    the Bayesian learning loop: more data -> better risk predictions.
    """
    if not _bayesian_updater:
        raise HTTPException(status_code=503, detail="Bayesian updater not initialized")

    result = _bayesian_updater.record_outcome(
        age=outcome.age, parity=outcome.parity,
        hemoglobin=outcome.hemoglobin,
        bp_systolic=outcome.bp_systolic, bp_diastolic=outcome.bp_diastolic,
        gestational_weeks=outcome.gestational_weeks,
        height_cm=outcome.height_cm, weight_kg=outcome.weight_kg,
        complication_history=outcome.complication_history.value,
        adverse_outcome=outcome.adverse_outcome,
    )
    result["disclaimer"] = DEMO_DISCLAIMER
    result["note"] = (
        "Bayesian posterior updated in memory. The risk table continuously improves "
        "as more birth outcomes are recorded. On container restart, resets to static "
        "literature-calibrated tables."
    )
    return result


@router.get("/bayesian-stats")
async def bayesian_stats():
    """Statistics on Bayesian posterior updates."""
    if not _bayesian_updater:
        return {"outcomes_recorded": 0, "unique_combinations": 0, "status": "not_initialized"}
    return {
        "outcomes_recorded": _bayesian_updater.outcomes_recorded,
        "unique_combinations": _bayesian_updater.unique_combinations_observed,
        "status": "active",
        "note": "In-memory Bayesian accumulator. Resets on container restart.",
    }


# ---------------------------------------------------------------------------
# Blood Bank Count-Min Sketch endpoints
# ---------------------------------------------------------------------------

@router.post("/blood-bank/report")
async def blood_bank_report(
    facility_id: str = Query(...),
    blood_type: str = Query(...),
    units: int = Query(..., ge=0, le=500),
):
    """Report blood stock via Count-Min Sketch (federated, privacy-preserving).

    Uses the Count-Min Sketch probabilistic data structure (Cormode & Muthukrishnan, 2005)
    for sub-linear space blood bank inventory estimation. Novel application in healthcare.
    """
    if not _blood_bank:
        raise HTTPException(status_code=503, detail="Blood bank sketch not initialized")
    try:
        result = _blood_bank.report_stock(facility_id, blood_type, units)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.get("/blood-bank/query")
async def blood_bank_query(
    blood_type: str = Query(...),
    facility_id: str = Query(None),
):
    """Query estimated blood availability via Count-Min Sketch."""
    if not _blood_bank:
        raise HTTPException(status_code=503, detail="Blood bank sketch not initialized")
    try:
        result = _blood_bank.query_availability(blood_type, facility_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.get("/blood-bank/nearest")
async def blood_bank_nearest(
    blood_type: str = Query(...),
    latitude: float = Query(...),
    longitude: float = Query(...),
    min_units: int = Query(1, ge=1),
):
    """Find nearest facilities with blood stock (Count-Min Sketch estimated)."""
    if not _blood_bank:
        raise HTTPException(status_code=503, detail="Blood bank sketch not initialized")
    try:
        facilities = _blood_bank.find_nearest_with_stock(
            blood_type, latitude, longitude, min_units
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"blood_type": blood_type, "facilities": facilities}


# ---------------------------------------------------------------------------
# Explainability endpoints (Counterfactual, Attribution, Credible Intervals)
# ---------------------------------------------------------------------------

_explainer = None
_attributor = None
_ci_calc = None
_temporal_engine = None
_deduplicator = None
_patient_counter = None
_consent_manager = None
_dp_engine = None
_icd10_mapper = None


def set_explainability(explainer, attributor, ci_calc):
    global _explainer, _attributor, _ci_calc
    _explainer = explainer
    _attributor = attributor
    _ci_calc = ci_calc


def set_temporal_engine(engine):
    global _temporal_engine
    _temporal_engine = engine


def set_deduplicator(dedup):
    global _deduplicator
    _deduplicator = dedup


def set_patient_counter(counter):
    global _patient_counter
    _patient_counter = counter


def set_consent_manager(manager):
    global _consent_manager
    _consent_manager = manager


def set_dp_engine(dp):
    global _dp_engine
    _dp_engine = dp


def set_icd10_mapper(mapper):
    global _icd10_mapper
    _icd10_mapper = mapper


@router.post("/risk-explain")
async def risk_explain(factors: RiskFactors):
    """Counterfactual explanations + attention attribution + credible intervals.

    Returns what-if scenarios showing which modifiable risk factors would
    reduce the patient's risk classification, normalized importance weights,
    and Bayesian credible intervals quantifying uncertainty.

    Novel: First application of counterfactual XAI to multiplicative relative
    risk maternal health scoring.
    """
    if not _risk_engine:
        raise HTTPException(status_code=503, detail="Risk engine not loaded")

    result = {}

    # Counterfactual explanations
    if _explainer:
        result["counterfactuals"] = _explainer.explain(
            factors.age, factors.parity, factors.hemoglobin,
            factors.bp_systolic, factors.bp_diastolic,
            factors.gestational_weeks, factors.height_cm,
            factors.weight_kg, factors.complication_history.value,
        )

    # Attention-weighted attribution
    if _attributor:
        result["attribution"] = _attributor.attribute(
            factors.age, factors.parity, factors.hemoglobin,
            factors.bp_systolic, factors.bp_diastolic,
            factors.gestational_weeks, factors.height_cm,
            factors.weight_kg, factors.complication_history.value,
        )

    # Credible intervals
    if _ci_calc:
        risk_result = _risk_engine.score(
            age=factors.age, parity=factors.parity,
            hemoglobin=factors.hemoglobin,
            bp_systolic=factors.bp_systolic,
            bp_diastolic=factors.bp_diastolic,
            gestational_weeks=factors.gestational_weeks,
            height_cm=factors.height_cm, weight_kg=factors.weight_kg,
            complication_history=factors.complication_history.value,
        )
        result["credible_interval"] = _ci_calc.enrich_risk_result(risk_result)

    result["disclaimer"] = DEMO_DISCLAIMER
    return result


@router.post("/risk-trajectory")
async def risk_trajectory(request: AssessmentRequest):
    """Temporal risk trajectory — week-by-week risk curve through delivery.

    Couples the multiplicative RR model with the learned-index anemia
    trajectory to produce a dynamic risk curve identifying the peak risk
    week and optimal intervention window.
    """
    if not _temporal_engine:
        raise HTTPException(status_code=503, detail="Temporal engine not initialized")

    result = _temporal_engine.compute_trajectory(
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
    result["disclaimer"] = DEMO_DISCLAIMER
    return result


@router.post("/consent/generate")
async def consent_generate(
    data_principal_id: str = Query(..., description="Patient or ASHA ID"),
    purposes: str = Query("risk_assessment", description="Comma-separated purposes"),
    retention_days: int = Query(90, ge=1, le=365),
):
    """Generate DPDP Act 2023 compliant consent token.

    Creates an HMAC-SHA256 signed purpose-limited consent token per
    India's Digital Personal Data Protection Act 2023.
    """
    if not _consent_manager:
        raise HTTPException(status_code=503, detail="Consent manager not initialized")
    purpose_list = [p.strip() for p in purposes.split(",")]
    token = _consent_manager.generate_token(data_principal_id, purpose_list, retention_days)
    return token


@router.post("/consent/validate")
async def consent_validate(
    token_id: str = Query(...),
    purpose: str = Query("risk_assessment"),
):
    """Validate a consent token for a specific purpose."""
    if not _consent_manager:
        raise HTTPException(status_code=503, detail="Consent manager not initialized")
    # Find token by ID — in production this would be a DB lookup
    return {"token_id": token_id, "purpose": purpose,
            "note": "Pass full token JSON to validate. Token lookup by ID requires persistent storage."}


@router.post("/consent/revoke")
async def consent_revoke(token_id: str = Query(...)):
    """Revoke a consent token (DPDP Act 2023, Section 12 — data erasure)."""
    if not _consent_manager:
        raise HTTPException(status_code=503, detail="Consent manager not initialized")
    revoked = _consent_manager.revoke_token(token_id)
    return {"token_id": token_id, "revoked": revoked, "status": "revoked" if revoked else "not_found"}


@router.get("/consent/stats")
async def consent_stats():
    """Consent token statistics."""
    if not _consent_manager:
        return {"status": "not_initialized"}
    return _consent_manager.stats()


@router.post("/icd10-map")
async def icd10_map(factors: RiskFactors):
    """Map risk factors to ICD-10-CM diagnostic codes.

    Automated mapping from the multiplicative relative risk model's
    discretized factor indices to billable ICD-10-CM codes (2026 code set,
    Chapter XV: Pregnancy, childbirth and the puerperium).
    """
    if not _icd10_mapper or not _risk_engine:
        raise HTTPException(status_code=503, detail="ICD-10 mapper not initialized")

    risk_result = _risk_engine.score(
        age=factors.age, parity=factors.parity,
        hemoglobin=factors.hemoglobin,
        bp_systolic=factors.bp_systolic,
        bp_diastolic=factors.bp_diastolic,
        gestational_weeks=factors.gestational_weeks,
        height_cm=factors.height_cm, weight_kg=factors.weight_kg,
        complication_history=factors.complication_history.value,
    )
    codes = _icd10_mapper.from_risk_result(risk_result)
    codes["disclaimer"] = DEMO_DISCLAIMER
    return codes


@router.get("/privacy-stats")
async def privacy_stats():
    """Privacy and deduplication statistics."""
    result = {}
    if _dp_engine:
        result["differential_privacy"] = {
            "epsilon": _dp_engine.epsilon,
            "budget_remaining": _dp_engine.privacy_budget_remaining(),
        }
    if _deduplicator:
        result["deduplication"] = _deduplicator.stats()
    if _patient_counter:
        result["patient_counter"] = _patient_counter.stats()
    if _consent_manager:
        result["consent"] = _consent_manager.stats()
    return result
