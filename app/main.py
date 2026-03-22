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
from app.api.v1.routes import router as v1_router, set_engines, set_real_facilities, set_assessment_store
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
        "google_maps_key": settings.google_maps_api_key,
    })


@app.get("/dashboard")
async def dashboard(request: FastAPIRequest):
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "google_maps_key": settings.google_maps_api_key,
    })


@app.get("/about")
async def about(request: FastAPIRequest):
    return templates.TemplateResponse("about.html", {"request": request})


@app.get("/pitch")
async def pitch(request: FastAPIRequest):
    return templates.TemplateResponse("pitch.html", {"request": request})
