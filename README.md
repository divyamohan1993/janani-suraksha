# 🏥 JananiSuraksha — AI-Powered Maternal Health Risk Intelligence

> Predicting which pregnancies will turn dangerous — before it's too late.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)]()
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)]()
[![Cloud Run](https://img.shields.io/badge/GCP-Cloud%20Run-blue.svg)]()
[![Terraform](https://img.shields.io/badge/IaC-Terraform-purple.svg)]()

**JananiSuraksha** converts India's ASHA worker network from a passive registration system into an active predictive intelligence network. Three O(1) engines — risk scoring, emergency referral routing, and anemia progression prediction — operate in constant time through aggressive precomputation, enabling instant maternal health risk assessment on any device.

🌐 **Live Demo**: [janani-suraksha on Cloud Run](https://janani-suraksha-pax2obvj3a-el.a.run.app)
📊 **Dashboard**: [District Health Officer View](https://janani-suraksha-pax2obvj3a-el.a.run.app/dashboard)
📖 **About**: [Full Product Story](https://janani-suraksha-pax2obvj3a-el.a.run.app/about)
🎯 **Pitch Deck**: [Investor Presentation](https://janani-suraksha-pax2obvj3a-el.a.run.app/pitch)
📡 **API Docs**: [Interactive API](https://janani-suraksha-pax2obvj3a-el.a.run.app/docs)

---

## The Problem

- **23,800 maternal deaths annually** in India — one every 22 minutes
- **1 million ASHA workers** visit every pregnant woman monthly
- **Zero** have an AI tool to predict which pregnancies will turn dangerous
- **80% of these deaths are preventable** (WHO)

## Three O(1) Engines

### Engine 1: Bayesian Risk Scoring
- 70,000 precomputed Beta-Binomial posterior entries
- 7 risk factors: age, parity, hemoglobin, BP, gestational week, BMI, complication history
- Single hash lookup → instant risk classification (Low/Medium/High/Critical)
- ~9MB in memory, <5ms response time

### Engine 2: Emergency Referral Routing
- 10,065 real health facilities from data.gov.in (Ministry of Health & Family Welfare) across 23 Indian states, with Google Maps geocoding and one-click navigation
- Precomputed Dijkstra shortest-path trees per capability level
- Routes to nearest FUNCTIONAL facility (not just nearest)
- Considers: specialist availability, blood bank, OT status

### Engine 3: Anemia Progression Prediction
- 7,480 hemoglobin trajectory profiles
- Predicts Hb at delivery based on current values and IFA compliance
- Shows compliance impact: "With 90% IFA, Hb improves from 7.2 to 9.8 g/dL"
- Early warning weeks before crisis

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ASHA Worker Interface                        │
│              (Tailwind CSS + Alpine.js)                         │
└──────────────────────┬──────────────────────────────────────────┘
                       │ HTTPS / JSON
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                  FastAPI Gateway (Cloud Run)                     │
│         Rate Limiting │ Auth │ Audit Log │ CSP Headers          │
└───────┬──────────────┼──────────────┬───────────────────────────┘
        │              │              │
        ▼              ▼              ▼
┌──────────────┐ ┌───────────┐ ┌──────────────┐
│ Engine 1:    │ │ Engine 2: │ │ Engine 3:    │
│ Risk Scoring │ │ Referral  │ │ Anemia       │
│ (70K entries)│ │ Routing   │ │ Prediction   │
│ O(1) lookup  │ │ (10,065   │ │ (7,480       │
│              │ │ facilities│ │ trajectories)│
│ Beta-Binomial│ │ Dijkstra  │ │ Learned      │
│ Posterior    │ │ SPTs)     │ │ Index)       │
└──────┬───────┘ └─────┬─────┘ └──────┬───────┘
       │               │              │
       ▼               ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│              Precomputed Data Layer (JSON, baked into image)     │
│   risk_table.json │ facility_graph.json │ hb_trajectories.json  │
└─────────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Alert Layer                                │
│        Risk Classification │ Referral │ Anemia Warnings         │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Local Development
```bash
# Set up environment variables
cp .env.example .env
# Edit .env — add your data.gov.in and Google Maps API keys

# Install dependencies
make install

# Generate precomputed O(1) data tables
make precompute

# Run locally
make run
# → http://localhost:8080
```

### Run Tests
```bash
make test
# 34/34 tests passing
```

### Docker
```bash
make build
docker run -p 8080:8080 janani-suraksha:latest
```

### Deploy to GCP (One-Click)
```bash
# Configure
cp infra/terraform.tfvars.example infra/terraform.tfvars
# Edit: project_id, region

# Deploy everything
make deploy
# → Outputs the live URL
```

### Tear Down
```bash
make destroy
```

## Project Structure

```
janani-suraksha/
├── app/
│   ├── main.py                          # FastAPI application entry point
│   ├── config.py                        # Settings and environment config
│   ├── security.py                      # Rate limiting, CSP, audit logging
│   ├── api/
│   │   └── v1/
│   │       └── routes.py                # API endpoint definitions
│   ├── engines/
│   │   ├── risk_scoring.py              # Engine 1: Bayesian risk scoring
│   │   ├── referral_routing.py          # Engine 2: Facility referral routing
│   │   └── anemia_prediction.py         # Engine 3: Anemia progression prediction
│   ├── models/
│   │   ├── schemas.py                   # Pydantic v2 request/response models
│   │   └── enums.py                     # Risk levels, capabilities, etc.
│   ├── precompute/
│   │   ├── generate_risk_table.py       # Generates 70K risk entries
│   │   ├── generate_facility_graph.py   # Generates facility network + SPTs
│   │   └── generate_hb_trajectories.py  # Generates Hb trajectory profiles
│   ├── static/
│   │   ├── css/custom.css
│   │   └── js/app.js
│   └── templates/
│       ├── index.html                   # ASHA Worker Assessment Interface
│       ├── dashboard.html               # District Health Officer Dashboard
│       ├── about.html                   # Full Product Story
│       └── pitch.html                   # Guy Kawasaki 10-Slide Pitch Deck
├── tests/
│   ├── conftest.py
│   ├── test_risk_scoring.py
│   ├── test_referral_routing.py
│   ├── test_anemia_prediction.py
│   └── test_api.py
├── infra/
│   ├── main.tf                          # Terraform provider config
│   ├── cloud_run.tf                     # Cloud Run service definition
│   ├── artifact_registry.tf             # Container registry
│   ├── variables.tf                     # Deployment variables
│   ├── outputs.tf                       # Service URL output
│   └── terraform.tfvars.example         # Example configuration
├── Dockerfile                           # Multi-stage, non-root build
├── Makefile                             # Build, test, deploy commands
└── requirements.txt                     # Python dependencies
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| API Framework | FastAPI (Python 3.12) |
| Validation | Pydantic v2 (strict mode) |
| Frontend | Tailwind CSS + Alpine.js |
| Container | Docker (multi-stage, non-root) |
| IaC | Terraform |
| Cloud | Google Cloud Run (scale-to-zero) |
| Registry | Google Artifact Registry |
| Facility Data | data.gov.in API (Real facility data) |
| Geocoding | Google Maps API (Geocoding + navigation) |

## Defense in Depth Security

Six security layers:
1. **Cloud Run IAM + HTTPS-only** (TLS 1.3)
2. **Rate limiting** (100 req/min per IP, sliding window)
3. **Pydantic strict input validation** with medical range checks
4. **CSP + CORS + Security headers**
5. **Audit logging** of every risk assessment
6. **Non-root container**, no PII in demo mode

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Health check + engine status |
| POST | `/api/v1/risk-score` | O(1) Bayesian risk scoring |
| POST | `/api/v1/referral` | O(1) emergency referral routing |
| POST | `/api/v1/anemia-predict` | O(1) anemia progression prediction |
| POST | `/api/v1/assessment` | Full ASHA worker assessment flow |
| GET | `/api/v1/facilities` | List all facilities |
| GET | `/api/v1/nearby-facilities` | Find nearby real facilities (data.gov.in) |

### Example: Full Assessment
```bash
curl -X POST https://janani-suraksha-pax2obvj3a-el.a.run.app/api/v1/assessment \
  -H "Content-Type: application/json" \
  -d '{
    "mother_name": "Sunita",
    "asha_id": "ASHA-001",
    "risk_factors": {
      "age": 26, "parity": 1, "hemoglobin": 8.5,
      "bp_systolic": 130, "bp_diastolic": 85,
      "gestational_weeks": 20, "height_cm": 157, "weight_kg": 55,
      "complication_history": "none"
    },
    "latitude": 27.57, "longitude": 80.68,
    "ifa_compliance": 0.6, "dietary_score": 0.5,
    "prev_anemia": false
  }'
```

## Pages

| Route | Description |
|-------|-------------|
| `/` | ASHA Worker Risk Assessment Interface |
| `/dashboard` | District Health Officer Dashboard |
| `/about` | Full Product Story |
| `/pitch` | Guy Kawasaki 10-Slide Pitch Deck |
| `/docs` | Interactive API Documentation |

## Cost

- **Cloud Run**: Scale-to-zero, min_instances=0 → ~$0/month at low traffic
- **Artifact Registry**: 60MB image, within free tier
- **No GPU** required at runtime
- **No database** — all data precomputed and baked into container
- **Facility data** is pre-fetched at build time — no runtime API cost for facility lookups

## Evidence Base & Limitations

**Real data**: Facility data (10,065 facilities) is sourced from data.gov.in (Government of India, Ministry of Health & Family Welfare). Geocoding is provided by Google Maps.

**What IS proven**: Bayesian conjugate priors, obstetric risk factors, Three Delays framework (validated 50+ countries)

**What needs validation**: Risk threshold calibration, ASHA adoption, MMR reduction (requires 18-month RCT). Risk scores and anemia predictions use approximate models that have not been clinically validated.

See the [About page](https://janani-suraksha-pax2obvj3a-el.a.run.app/about) for the full honest assessment.

## Roadmap

- [x] Three O(1) engines (70K + 10,065 real facilities + 7,480 entries)
- [x] Full-stack web application on GCP Cloud Run
- [x] 34/34 tests passing, defense-in-depth security
- [x] Terraform IaC — one-click deploy
- [ ] Pilot district partnership (targeting Q3 2026)
- [ ] ASHA worker usability study
- [ ] Cluster-randomized controlled trial
- [ ] Patent filing under India CRI Guidelines 2025

## License

MIT License — see [LICENSE](LICENSE) for details.

## Author

**Divya Mohan** — [dmj.one](https://dmj.one)

*Dream. Manifest. Journey. Together as one.*

*Vision: Aatmnirbhar Viksit Bharat 2047*

---

> **Patent Pending** — O(1) Bayesian Maternal Risk Scoring, Precomputed Facility-Capability Routing, and Learned Index Hemoglobin Trajectory Prediction.
