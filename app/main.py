"""JananiSuraksha - AI-Powered Maternal Health Risk Intelligence Platform."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request as FastAPIRequest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.security import RateLimitMiddleware, SecurityHeadersMiddleware, AuditLogMiddleware
from app.engines.risk_scoring import RiskScoringEngine
from app.engines.referral_routing import ReferralRoutingEngine
from app.engines.anemia_prediction import AnemiaPredictionEngine
from app.engines.real_facilities import RealFacilityFinder
from app.engines.bayesian_updater import BayesianUpdater
from app.engines.blood_bank_sketch import BloodBankSketch
from app.engines.risk_explainer import CounterfactualExplainer, AttentionWeightedAttribution, CredibleIntervalCalculator
from app.engines.temporal_risk import TemporalRiskEngine
from app.engines.bloom_filter import AssessmentDeduplicator
from app.engines.hyperloglog import PatientCounter
from app.engines.consent_manager import ConsentManager
from app.engines.differential_privacy import DifferentialPrivacy
from app.engines.icd10_mapper import ICD10Mapper
from app.api.v1.routes import (
    router as v1_router, set_engines, set_real_facilities, set_assessment_store,
    set_bayesian_updater, set_blood_bank, set_explainability, set_temporal_engine,
    set_deduplicator, set_patient_counter, set_consent_manager, set_dp_engine,
    set_icd10_mapper,
)
from app.persistence import AssessmentStore
from app.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("janani")

# Engine instances
risk_engine = RiskScoringEngine()
referral_engine = ReferralRoutingEngine()
anemia_engine = AnemiaPredictionEngine()
real_facility_finder = None  # Initialized in lifespan with config keys


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load all O(1) engines at startup."""
    settings = get_settings()
    data_dir = Path(__file__).parent.parent / "data"

    logger.info("Loading O(1) engines...")

    risk_path = data_dir / "risk_table.json"
    if risk_path.exists():
        risk_engine.load(str(risk_path))
        logger.info(f"Risk scoring engine loaded: {risk_engine.table_size} entries")
    else:
        logger.warning(f"Risk table not found at {risk_path} — using on-the-fly computation")
        risk_engine._loaded = True  # Allow fallback computation

    facility_path = data_dir / "facility_graph.json"
    if facility_path.exists():
        referral_engine.load(str(facility_path))
        logger.info(f"Referral routing engine loaded: {referral_engine.facility_count} facilities")
    else:
        logger.warning(f"Facility graph not found at {facility_path}")
        referral_engine._loaded = True

    hb_path = data_dir / "hb_trajectories.json"
    if hb_path.exists():
        anemia_engine.load(str(hb_path))
        logger.info(f"Anemia prediction engine loaded: {anemia_engine.trajectory_count} trajectories")
    else:
        logger.warning(f"Hb trajectories not found at {hb_path}")
        anemia_engine._loaded = True

    set_engines(risk_engine, referral_engine, anemia_engine)

    # Initialize Bayesian posterior updater wrapping risk engine
    bayesian_updater = BayesianUpdater(risk_engine)
    set_bayesian_updater(bayesian_updater)
    logger.info("Bayesian posterior updater initialized (in-memory, resets on restart).")

    # Initialize Blood Bank Count-Min Sketch
    # Cormode & Muthukrishnan (2005) — width=256, depth=4 gives
    # error bound e/256 * N ≈ 1.06% of total updates with 98.2% confidence
    blood_bank = BloodBankSketch(width=256, depth=4)

    # Register all facilities from referral engine into the blood bank network
    for facility in referral_engine.get_all_facilities():
        blood_bank.register_facility(
            facility_id=facility["facility_id"],
            name=facility["name"],
            latitude=facility["latitude"],
            longitude=facility["longitude"],
            district=facility.get("facility_id", "").split("-")[1] if "-" in facility.get("facility_id", "") else "",
        )

    # Seed with demo stock data based on facility blood_bank_status
    import random
    random.seed(42)  # Deterministic demo data
    blood_types = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
    # Indian blood type distribution (approx): O+ 36%, B+ 28%, A+ 22%, AB+ 7%
    # Negative types are ~8% of each positive type
    stock_weights = {"O+": 1.0, "B+": 0.85, "A+": 0.75, "AB+": 0.5,
                     "O-": 0.3, "B-": 0.25, "A-": 0.2, "AB-": 0.15}
    for facility in referral_engine.get_all_facilities():
        fid = facility["facility_id"]
        status = facility.get("blood_bank_status", "unavailable")
        if status == "unavailable":
            continue
        for bt in blood_types:
            base = 20 if status == "available" else 8  # low_stock
            units = max(0, int(base * stock_weights[bt] + random.randint(-3, 5)))
            if units > 0:
                blood_bank.report_stock(fid, bt, units)

    set_blood_bank(blood_bank)
    logger.info(f"Blood bank CMS initialized: {blood_bank.registered_facilities} facilities, "
                f"{blood_bank.total_updates} stock reports seeded")

    # Initialize assessment persistence
    assessment_store = AssessmentStore()
    set_assessment_store(assessment_store)
    logger.info("Assessment persistence store initialized.")

    global real_facility_finder
    real_facility_finder = RealFacilityFinder(
        google_maps_key=settings.google_maps_api_key,
        data_gov_key=settings.data_gov_api_key,
    )
    real_facilities_path = data_dir / "real_facilities.json"
    if real_facilities_path.exists():
        real_facility_finder.load(str(real_facilities_path))
    else:
        logger.warning(f"Real facility data not found at {real_facilities_path}")
    set_real_facilities(real_facility_finder)
    logger.info(f"Real facility finder: {real_facility_finder.total_facilities} facilities, "
                f"Google Maps geocoding: {'enabled' if settings.google_maps_api_key else 'disabled'}")
    # Initialize explainability engines (Counterfactual, Attribution, Credible Intervals)
    explainer = CounterfactualExplainer(risk_engine)
    attributor = AttentionWeightedAttribution(risk_engine)
    ci_calc = CredibleIntervalCalculator()
    set_explainability(explainer, attributor, ci_calc)
    logger.info("Explainability engines initialized (counterfactual, attribution, credible intervals).")

    # Initialize temporal risk trajectory engine
    temporal_engine = TemporalRiskEngine(risk_engine, anemia_engine)
    set_temporal_engine(temporal_engine)
    logger.info("Temporal risk trajectory engine initialized.")

    # Initialize privacy engines
    consent_manager = ConsentManager()
    dp_engine = DifferentialPrivacy(epsilon=1.0)
    set_consent_manager(consent_manager)
    set_dp_engine(dp_engine)
    logger.info("Privacy engines initialized (DPDP consent manager, differential privacy epsilon=1.0).")

    # Initialize probabilistic data structures
    deduplicator = AssessmentDeduplicator(window_hours=24)
    patient_counter = PatientCounter()
    set_deduplicator(deduplicator)
    set_patient_counter(patient_counter)
    logger.info("Probabilistic DS initialized (Bloom filter dedup, HyperLogLog patient counter).")

    # Initialize ICD-10 mapper
    icd10_mapper = ICD10Mapper()
    set_icd10_mapper(icd10_mapper)
    logger.info("ICD-10-CM mapper initialized (2026 code set, Chapter XV).")

    logger.info("All engines ready.")

    yield

    logger.info("Shutting down JananiSuraksha.")


# Create app
app = FastAPI(
    title="JananiSuraksha",
    description="AI-Powered Maternal Health Risk Intelligence & Safe Delivery Navigator",
    version="1.0.0",
    lifespan=lifespan,
)

# Defense in depth: security middleware stack (order matters - outermost first)
settings = get_settings()
app.add_middleware(AuditLogMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, max_requests=settings.rate_limit_per_minute, window_seconds=60)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Routes
app.include_router(v1_router)

# Static files and templates
static_dir = Path(__file__).parent / "static"
templates_dir = Path(__file__).parent / "templates"

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

templates = Jinja2Templates(directory=str(templates_dir))


@app.get("/")
async def home(request: FastAPIRequest):
    return templates.TemplateResponse("index.html", {
        "request": request,
    })


@app.get("/dashboard")
async def dashboard(request: FastAPIRequest):
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
    })


@app.get("/about")
async def about(request: FastAPIRequest):
    return templates.TemplateResponse("about.html", {"request": request})


@app.get("/pitch")
async def pitch(request: FastAPIRequest):
    return templates.TemplateResponse("pitch.html", {"request": request})
