# Patent Technical Intake Sheet — JananiSuraksha

**Invention:** JananiSuraksha — AI-Powered Maternal Health Risk Intelligence & Safe Delivery Navigator
**Drafted by:** Divya Mohan
**Initiative:** dmj.one — *Dream. Manifest. Journey. Together as one.*

---

## *Define the problem and its relevance to today's market / society / industry need (Max: 100 Words)

India records ~19,000 maternal deaths annually (UN-MMEIG 2023), with MMR of 88 per 100,000 live births (SRS 2021-23). Hemorrhage (41.3%), hypertensive disorders (18.6%), and anemia drive mortality (India MDSR). Despite ~1 million ASHA workers visiting every pregnant woman monthly, none carry predictive risk tools. The "three delays" framework (Thaddeus & Maine, 1994) — deciding to seek care, reaching a facility, receiving treatment — persists because 79.5% specialist positions at CHCs remain vacant (Rural Health Statistics 2021-22), and 52.2% of pregnant women are anemic (NFHS-5, 2019-21). WHO confirms most maternal deaths are preventable.

---

## *Describe the Solution / Proposed / Developed (Max: 100 Words)

JananiSuraksha deploys three integrated precomputed engines on ASHA worker smartphones in a closed-loop pipeline: (1) **Risk Scoring** — 70,000 precomputed multiplicative relative risk entries mapping 7 clinical dimensions to risk classification via hash lookup; (2) **Anemia Prediction** — learned index MLP (2,497 parameters; Kraska et al., SIGMOD 2018) predicting hemoglobin trajectory, whose output feeds back to re-score risk with projected delivery Hb; (3) **Referral Routing** — risk level auto-maps to required facility capability (EmOC framework), then precomputed spatial index routes to the nearest matching facility. Blood bank availability enriched via Count-Min Sketch.

---

## *Explain the uniqueness and distinctive features of the (product / process / service) solution (Max: 100 Words)

To the best of the applicant's knowledge, no existing maternal health platform integrates precomputed risk scoring, facility-capability routing, and learned-index hemoglobin prediction in a closed-loop pipeline where each engine's output drives the next. The specific integration is novel: predicted hemoglobin trajectory (Engine 3) feeds back to re-evaluate risk (Engine 1); risk level auto-selects facility capability via the EmOC framework; capability drives spatial routing (Engine 2). This produces context-aware referrals with temporal risk awareness that no individual engine achieves alone. All intelligence is precomputed at build time — no GPU, database, or network dependency at runtime.

---

## *How your proposed / developed solution is different from similar kind of product by the competitors if any (Max: 100 Words)

PIERS on the Move (UBC, 2014) predicts pre-eclampsia only via real-time logistic regression; no facility routing. SMARThealth Pregnancy uses rule-based decision trees, not computed risk scores. ARMMAN/mMitra predicts program dropout, not clinical risk. CommCare provides case management without predictive engines. OpenSRP digitizes guidelines without risk computation. Delfina targets US health plans, requires EHR. CareNX requires proprietary hardware. None integrates: (a) precomputed multi-dimensional risk scoring with Hb-trajectory feedback, (b) risk-driven facility-capability routing via precomputed spatial index, (c) learned-index anemia prediction — all in a stateless container with no runtime dependencies.

---

## *Has the Solution Received any Innovation Grant/Seed fund Support? If yes, please mention.

NO

---

## *Utility: Highlight the utility/value proposition (key benefits) aspects of the solution/innovation (Max: 100 Words)

JananiSuraksha converts India's ASHA network from passive data collectors into predictive intelligence agents. Risk classification enables evidence-backed urgency communication — addressing Delay 1 (Thaddeus & Maine, 1994). Facility-capability routing ensures patients reach facilities with required capabilities (not just nearest ones — 74.2% OB-GYN vacancy per RHS 2021-22) — addressing Delay 2. Predicted hemoglobin trajectory warns weeks before crisis: projected Hb decline re-scores risk upward, auto-escalating the required facility capability. IFA compliance intervention can reduce anemia prevalence by 70% at term (Peña-Rosas, Cochrane 2015). Voice input in 12 Indian languages via browser Speech API.

---

## *Scalability: Highlight the market potential aspects of the Solution/Innovation (Max: 100 Words)

India's ~24 million annual pregnancies served by ~1 million ASHAs represent the immediate addressable market. Government infrastructure is ready: 799 million ABHA digital health IDs (ABDM, August 2025); JSY allocates Rs 1,814 crore/year for maternal health (NHM Financial Management Report, MoHFW). Scale-to-zero serverless architecture enables high-volume assessments at minimal cost — all intelligence precomputed at build time, requiring no GPU, database, or ML retraining at runtime. The platform is extensible to other LMIC maternal health contexts where community health workers face similar infrastructure constraints.

---

## *Economic Sustainability: Highlight commercialisation/business application aspects of the solution (Max: 100 Words)

Serverless scale-to-zero architecture eliminates idle infrastructure costs. Revenue models: (1) NHM/ABDM integration under government digital health programs; (2) per-district SaaS licensing; (3) per-assessment transaction model. Economic justification: each prevented maternal death averts significant household income loss (WHO Commission on Macroeconomics and Health, 2001; Lancet Maternal Health Series, 2016). India's maternal health spending under NHM: Rs 39,435 crore ($4.7B) for FY 2025-26 (Union Budget 2025-26, Ministry of Finance). All intelligence precomputed into static data structures enables stateless horizontal scaling with near-zero marginal cost per assessment.

---

## *Environmental Sustainability: Highlight environmental friendliness aspects and related benefit of the solution/innovation (Max: 100 Words)

JananiSuraksha replaces paper-based MCP cards and 7+ registers maintained by ~1 million ASHAs — currently consuming 41 minutes/day in documentation (Kaur J et al., PMC 2023, PMC10746798). Scale-to-zero serverless architecture consumes zero compute when idle, deployed on infrastructure with PUE 1.09 (vs industry average 1.56; Google Environmental Report 2024). Cloud migration reduces carbon footprint by up to 88% versus on-premise (451 Research/AWS, "The Carbon Reduction Opportunity of Moving to Amazon Web Services", 2019). Precomputed architecture eliminates GPU-intensive real-time inference, minimizing energy consumption per assessment.

---

## Section 3(k) Defense: Technical Effect Beyond Computer Program Per Se

Under Section 3(k) of the Patents Act, 1970, a "computer programme per se" is not patentable. JananiSuraksha's claims extend beyond software to produce demonstrable technical effects, assessed under the Indian Patent Office's 2025 CRI Guidelines three-step test:

**Step 1 — Understand the invention as a whole:** The invention is a technical architecture for deploying predictive clinical intelligence on resource-constrained devices over unreliable networks. The inventive concept is the precomputation-at-build-time / lookup-at-runtime closed-loop pipeline that eliminates GPU, database, and reliable network dependencies while maintaining engine-to-engine integration.

**Step 2 — Technical solution, not commercial strategy:** The system solves a technical problem: how to provide sub-second clinical risk prediction with Hb-trajectory feedback, facility-capability routing, and blood bank inventory estimation on smartphones with intermittent connectivity and no backend database. The solution — precomputing 70,000 risk entries, 46,013 spatial grid cells, and 7,480 hemoglobin trajectories into static data structures served from a stateless container — is a technical architecture decision producing measurable performance characteristics (sub-5ms risk lookup, bounded-time trajectory prediction, single-request integrated assessment).

**Step 3 — Patentability determination under technical effect doctrine:**

1. **Physical domain operation:** The system processes physiological measurements (hemoglobin concentration in blood, systolic/diastolic blood pressure, body mass index) and geographic coordinates of real physical facilities — not abstract data. Outputs route patients to specific named hospitals verified to have required medical capabilities.

2. **Closed-loop integration producing synergistic technical effect:** The three engines form a pipeline where each engine's output materially changes the computation of the next (`app/api/v1/routes.py`, lines 172-340):
   - Engine 1 (risk scoring) produces initial risk classification
   - Engine 3 (anemia prediction) produces predicted delivery hemoglobin
   - Engine 1 (re-score) re-evaluates risk using projected Hb — upgrading risk level if trajectory worsens
   - Risk level auto-maps to facility capability requirement (EmOC framework: critical→comprehensive_emoc, high→blood_transfusion, medium→basic_emoc)
   - Engine 2 (referral routing) uses capability requirement + GPS to find nearest matching facility from precomputed spatial index
   - Count-Min Sketch enriches referral with probabilistic blood bank availability estimate

   This closed-loop integration produces context-aware facility matching with temporal risk awareness — a technical effect that no individual engine achieves alone.

3. **Technical contribution to constrained deployment:** The precomputed architecture constitutes a technical solution to the engineering problem of deploying predictive maternal health intelligence in India's ASHA worker context (basic smartphones, 2G/3G networks, no GPU, no database). This is analogous to the Niramai Health Analytix precedent (multiple Indian and international patents granted, incl. WO2017145125A1, for AI processing physical thermal measurements to produce clinical diagnostic output).

4. **Probabilistic data structures for real-time resource estimation:** Count-Min Sketch (width=256, depth=4) provides sub-linear space blood bank inventory estimation queried during the assessment flow. Laplace mechanism differential privacy (Dwork, ICALP 2006) privatizes aggregate dashboard statistics — applied to the `/dashboard-stats` endpoint before sharing, preventing re-identification from small-area health aggregates. Both are technical implementations operating on physical healthcare resource data.

---

## Prior Art Distinction

### vs. PIERS on the Move (UBC PRE-EMPT, 2014-2017)
POM is mobile pre-eclampsia risk prediction deployed with ASHAs in Karnataka (CLIP Trial). Distinguished:
- POM predicts **single condition** (pre-eclampsia) via real-time logistic regression. JananiSuraksha scores **comprehensive maternal risk** across 7 dimensions covering all major mortality causes.
- POM has **no facility-capability routing** — only "refer vs. don't refer." JananiSuraksha auto-maps risk level to required EmOC capability and routes to the nearest facility with that capability.
- POM has **no hemoglobin trajectory prediction** and no feedback loop.
- POM requires internet for real-time inference. JananiSuraksha precomputes all intelligence at build time.

### vs. SMARThealth Pregnancy (George Institute, 2022-2023)
Tablet-based CDSS for ASHAs screening for anemia, hypertension, GDM. Distinguished:
- Uses **rule-based decision trees** (digitized WHO guidelines), not computed numerical risk scores.
- **No precomputed data structures** — relies on if/then logic.
- **No hemoglobin trajectory prediction**, no facility-capability matching, no learned index.

### vs. Kraska et al. Learned Index (SIGMOD 2018)
The learned index algorithm is prior art. The novelty is not the MLP architecture but:
- The **5-feature maternal health encoding** (initial_hb, gestational_weeks, ifa_compliance, dietary_score, prev_anemia) and physiologically-parameterized training data (7,480 profiles from Bothwell 2000, Hytten 1985, Peña-Rosas/Cochrane 2015).
- The **integration** of learned index output as a dynamic risk modifier in the closed-loop assessment pipeline — predicted Hb feeds back to re-score risk, which in turn changes facility capability selection.
- The ability to serve predictions from a **68 KB weight file** with no runtime ML framework dependency.

---

## Technical Architecture Summary

### Integrated Assessment Pipeline (`app/api/v1/routes.py`, lines 172-340)

```
User Input → Engine 1 (Risk Score, initial)
                    ↓
             Engine 3 (Anemia Prediction) → predicted delivery Hb
                    ↓
             Engine 1 (Re-score with projected Hb)  ← FEEDBACK LOOP
                    ↓
             Risk level → Capability mapping (EmOC framework)
                    ↓
             Engine 2 (Precomputed spatial routing) ← capability + GPS
                    ↓
             Blood Bank CMS query ← facility from Engine 2
                    ↓
             Integrated Response (risk + trajectory + referral + blood bank)
```

**Risk-to-Capability Mapping** (based on WHO/UNFPA/UNICEF/AMDD EmOC framework, 2009):
| Risk Level | Required Capability | Rationale |
|-----------|-------------------|-----------|
| Critical | comprehensive_emoc | C-section + blood transfusion capability required |
| High | blood_transfusion | Functional blood bank required |
| Medium | basic_emoc | Basic emergency obstetric care |
| Low | basic_emoc | Routine ANC facility |

### Engine 1: Risk Scoring (`app/engines/risk_scoring.py`)
- **Precomputed entries:** 70,000 (verified: `data/risk_table.json`, 33 MB)
- **Dimensions:** 7 — age(5) × parity(4) × Hb(5) × BP(5) × gest_weeks(7) × BMI(4) × complications(5) = 70,000
- **Lookup mechanism:** SHA-256 hash of 7-byte discretized tuple → 16-char hex key → Python dict lookup
- **Risk levels:** Low (<1%), Medium (1-5%), High (5-15%), Critical (≥15%)
- **Base rate:** 0.005 (SRS 2019-21 MMR + WHO severe morbidity 5:1 ratio)
- **Runtime modifiers:** IFA compliance (1.0-1.3×), dietary score (1.0-1.2×), previous anemia (1.5×)
- **Interaction terms:** Synergistic multipliers for correlated risk factors (anemia+PPH, HTN+eclampsia)
- **Hb feedback:** If Engine 3 predicts delivery Hb lower than current, Engine 1 re-scores with projected value; operative risk is the worse of current vs. projected

### Engine 2: Referral Routing (`app/engines/referral_routing.py`)
- **Facilities in spatial index:** 10,602 geocoded in the exemplary embodiment (`data/facility_graph.json`, 106 MB)
- **Total facilities parsed from data.gov.in:** 28,128 across 36 states (`data/real_facilities.json`)
- **data.gov.in resource ID:** 37670b6f-c236-49a7-8cd7-cc2dc610e32d
- **Grid resolution:** 0.1 degrees (~11 km cells)
- **Precomputed grid cells:** 46,013 per capability level in the exemplary embodiment
- **Capability levels:** 5 — basic_emoc, comprehensive_emoc, blood_transfusion, c_section, neonatal_icu
- **Per cell:** Primary facility + backup (2nd-nearest) precomputed via shortest path tree
- **Blood banks:** 2,484 real blood banks from data.gov.in (resource fced6df9-a360-4e08-8ca0-f283fc74ce15)
- **Input from Engine 1:** Risk level determines minimum capability requirement via EmOC mapping

### Engine 3: Anemia Prediction (`app/engines/learned_index.py`)
- **Architecture:** Linear(5,64) → ReLU → Linear(64,32) → ReLU → Linear(32,1) → Sigmoid
- **Parameters:** 2,497 (verified: `data/learned_index_weights.json`, 68 KB)
- **Trajectories:** 7,480 literature-derived profiles (verified: `data/hb_trajectories.json`, 7 MB)
- **Grid composition:** 17 Hb levels × 11 gestational weeks × 5 IFA compliance × 4 dietary scores × 2 prev_anemia = 7,480
- **Input features:** initial_hb, gestational_weeks, ifa_compliance, dietary_score, prev_anemia
- **Mechanism:** MLP predicts position in sorted trajectory array; bounded local search (±max_error) refines match
- **Physiological model:** Linear Hb decline (Bothwell 2000) + Gaussian hemodilution nadir at week 30 (Hytten 1985) + IFA effect (Peña-Rosas/Cochrane 2015) + dietary effect (Haider & Bhutta/Cochrane 2017)
- **Classification:** WHO anemia thresholds — Severe <7, Moderate 7-9.9, Mild 10-10.9, Normal ≥11 g/dL (WHO/NMH/NHD/MNM/11.1, 2011)
- **Reference:** Kraska T et al., "The Case for Learned Index Structures", SIGMOD 2018
- **Output to Engine 1:** Predicted delivery Hb feeds back to re-score risk

### Supporting Engines
- **Bayesian Updater** (`app/engines/bayesian_updater.py`): Beta-Binomial conjugate posterior updating for regional risk calibration from observed birth outcomes. Thread-safe (threading.Lock). Currently in-memory; persistence backend planned for production deployment.
- **Count-Min Sketch** (`app/engines/blood_bank_sketch.py`): Probabilistic data structure (width=256, depth=4) for blood bank availability estimation across 2,484 facilities and 8 blood types. Queried during the assessment flow for referrals requiring blood_transfusion or comprehensive_emoc capability. Error bound: ε/256 × N ≈ 1.06%.
- **Differential Privacy** (`app/engines/differential_privacy.py`): Laplace mechanism (Dwork, ICALP 2006) applied to the `/dashboard-stats` endpoint, adding calibrated noise to aggregate health counts before sharing. Epsilon=1.0, sequential composition tracking, aligned with DPDP Act 2023 (Sections 4(2), 8(7)).

### Voice Interface (`app/templates/index.html`)
- **Implementation:** Browser Web Speech API (SpeechRecognition) — a user interface feature, not part of the inventive architecture
- **Languages:** 12 — Hindi (hi-IN), English (en-IN), Tamil (ta-IN), Telugu (te-IN), Bengali (bn-IN), Marathi (mr-IN), Gujarati (gu-IN), Kannada (kn-IN), Malayalam (ml-IN), Punjabi (pa-IN), Odia (or-IN), Assamese (as-IN)
- **Fallback:** Manual form entry when Speech API unavailable

### Deployment
- **Platform:** Serverless compute platform with scale-to-zero capability (min_instances=0)
- **Build:** Multi-stage Docker — precomputes all data at build time, ships as static JSON
- **Runtime:** Python 3.12-slim, non-root user, no database, no external API dependencies for core engines
- **Security:** Rate limiting, CSP headers, audit logging

### Conditional Pipeline Activation
- Engine 3 (anemia prediction) is invoked when current hemoglobin falls below the WHO normal threshold for pregnancy (11.0 g/dL, per WHO/NMH/NHD/MNM/11.1, 2011). For women with normal hemoglobin (≥11.0 g/dL), anemia trajectory prediction is clinically unnecessary and is not performed — mirroring standard clinical triage where anemia workup is indicated only for sub-normal values.
- The Hb feedback loop activates only when predicted delivery hemoglobin declines below the current value — i.e., when the trajectory worsens. If the trajectory is stable or improving (e.g., with good IFA compliance), the initial risk score stands without adjustment.
- Engine 2 (referral routing) is invoked for medium, high, and critical risk levels. Low-risk patients receive routine ANC scheduling without facility-capability routing, consistent with India's NHM guidelines for low-risk pregnancy management.

### Scope Clarification
- The system addresses **Delay 1** (decision to seek care) and **Delay 2** (reaching appropriate facility) of the Thaddeus & Maine framework. **Delay 3** (receiving adequate treatment at the facility) is outside system scope.
- Build-time data counts (10,602 facilities, 46,013 grid cells, 2,484 blood banks) reflect the data.gov.in dataset in the exemplary embodiment and may vary with subsequent builds.
- The multiplicative risk model assumes conditional independence across dimensions, with interaction terms applied for known correlated factor pairs to partially mitigate this assumption.
- No prospective clinical validation has been conducted. The system is designed as decision-support pending field validation via clinical trial. Risk factor weights are derived from published peer-reviewed meta-analyses and systematic reviews (see Citations Index).

---

## Citations Index

### Maternal Mortality & Epidemiology
| Citation | Source | Verification |
|----------|--------|-------------|
| MMR 88 per 100,000 (2021-23) | SRS Special Bulletin on Maternal Mortality, ORGI, Ministry of Home Affairs | Verified — censusindia.gov.in |
| ~19,000 deaths/year (2023) | UN Maternal Mortality Estimation Inter-agency Group (MMEIG), "Trends in Maternal Mortality 2000-2023", published April 7, 2025 | Verified — PIB PRID=2128024 |
| Hemorrhage 41.3%, Hypertensive 18.6%, Anemia 17.5% | India Maternal Death Surveillance and Response (MDSR), NHM Guidelines | Verified — nhm.gov.in |
| "Most maternal deaths are preventable" | WHO Maternal Mortality Fact Sheet, updated 2024 | Verified — who.int |
| Three delays model | Thaddeus S, Maine D. "Too far to walk: maternal mortality in context." Soc Sci Med. 1994;38(8):1091-1110 | DOI: 10.1016/0277-9536(94)90226-7, PMID: 8042057 |
| 52.2% pregnant women anemic | National Family Health Survey-5 (NFHS-5, 2019-21), International Institute for Population Sciences (IIPS), MoHFW | Verified — rchiips.org/nfhs |
| 79.5% specialist vacancy at CHCs | Rural Health Statistics 2021-22, Statistics Division, MoHFW, Government of India | Verified — mohfw.gov.in |
| 74.2% OB-GYN vacancy at CHCs | Rural Health Statistics 2021-22, Statistics Division, MoHFW | Verified |
| EmOC framework for facility capabilities | WHO/UNFPA/UNICEF/AMDD, "Monitoring Emergency Obstetric Care: A Handbook", 2009 | ISBN: 978-92-4-154773-4 |

### Risk Factor Evidence Base
| Risk Factor | Citation | DOI/PMID | RR Used | Note |
|-------------|----------|----------|---------|------|
| Age <18 | Ganchimeg T et al., BJOG 2014;121(s1):40-48 | DOI: 10.1111/1471-0528.12630, PMID: 24641534 | 3.0 | Upper-bound estimate for composite adverse outcomes |
| Age >35 | Lean SC et al., PLoS One 2017;12(10):e0186287 | DOI: 10.1371/journal.pone.0186287, PMID: 29040334 | 3.5 | |
| Severe anemia <7 g/dL | Daru J et al., Lancet Glob Health 2018;6(5):e548-e554 | DOI: 10.1016/S2214-109X(18)30078-0, PMID: 29571592 | 8.0 | Composite severe adverse maternal outcomes |
| Stage 2 HTN | Abalos E et al., BJOG 2014;121(s1):14-24 | DOI: 10.1111/1471-0528.12629, PMID: 24641531 | 5.0 | |
| Hypertensive crisis (SBP≥180/DBP≥120) | Say L et al., Lancet Glob Health 2014;2(6):e323-e333 | DOI: 10.1016/S2214-109X(14)70227-X, PMID: 25103301 | 15.0 | |
| IFA supplementation | Peña-Rosas JP et al., Cochrane Database Syst Rev 2015;(7):CD004736 | DOI: 10.1002/14651858.CD004736.pub5, PMID: 26198451 | 70% reduction in anemia prevalence at term |
| Hb changes in pregnancy | Bothwell TH, Am J Clin Nutr 2000;72(1S):257S-264S | DOI: 10.1093/ajcn/72.1.257S, PMID: 10871591 | — |
| Hemodilution peak wk 30 | Hytten F, Clin Haematol 1985;14(3):601-612 | PMID: 4075604 | — |
| Previous PPH recurrence | Ford JB et al., Med J Aust 2007;187(7):391-393 | DOI: 10.5694/j.1326-5377.2007.tb01308.x, PMID: 17908001 | 4.0 | |
| Previous eclampsia recurrence | Sibai BM, Obstet Gynecol 2005;105(2):402-410 | DOI: 10.1097/01.AOG.0000152351.13671.99, PMID: 15684172 | 5.0 | |
| Obesity BMI >30 | Marchi J et al., Obes Rev 2015;16(8):621-638 | DOI: 10.1111/obr.12288, PMID: 26016557 | 2.0 | |
| WHO anemia thresholds | WHO/NMH/NHD/MNM/11.1 (2011) | who.int | <7/7-9.9/10-10.9/≥11 g/dL | |

### Computer Science & Data Structures
| Innovation | Citation | DOI |
|-----------|----------|-----|
| Learned Index Structures | Kraska T, Beutel A, Chi EH, Dean J, Polyzotis N. "The Case for Learned Index Structures." SIGMOD 2018:489-504 | DOI: 10.1145/3183713.3196909 |
| Count-Min Sketch | Cormode G, Muthukrishnan S. "An improved data stream summary: The count-min sketch and its applications." J Algorithms 2005;55(1):58-75 | DOI: 10.1016/j.jalgor.2003.12.001 |
| Differential Privacy | Dwork C. "Differential Privacy." ICALP 2006, LNCS vol 4052:1-12 | DOI: 10.1007/11787006_1 |

### Government & Institutional Data
| Data Point | Value | Source | Verification |
|-----------|-------|--------|-------------|
| JSY expenditure (FY 2023-24) | Rs 1,814 crore ($217M) | NHM Financial Management Report, MoHFW, Government of India | nhm.gov.in |
| NHM total allocation (FY 2025-26) | Rs 39,435 crore ($4.7B) | Union Budget 2025-26, Ministry of Finance, Government of India | indiabudget.gov.in |
| ABDM: ABHA IDs created (as of Aug 2025) | 799 million | Press Information Bureau (PIB), MoHFW official statement | pib.gov.in |
| Economic cost of maternal mortality | Significant household income loss; GDP impact | WHO Commission on Macroeconomics and Health (2001); Lancet Maternal Health Series (2016) | DOI: 10.1016/S0140-6736(16)31534-3 |

### Prior Art References
| System | Citation | Overlap | Distinction |
|--------|----------|---------|-------------|
| PIERS on the Move | von Dadelszen P et al., JMIR mHealth uHealth 2015;3(2):e37. DOI: 10.2196/mhealth.3942 | Mobile risk prediction for ASHAs in India | Single-condition (pre-eclampsia), real-time logistic regression, no facility routing, no Hb trajectory |
| SMARThealth Pregnancy | Praveen D et al., JMIR Formative Research 2023;7:e44713. DOI: 10.2196/44713 | Tablet-based CDSS for ASHAs | Rule-based decision trees, no computed risk scores, no precomputed data structures |
| miniPIERS | Payne BA et al., PLoS Medicine 2014;11(1):e1001589. DOI: 10.1371/journal.pmed.1001589 | Simplified pre-eclampsia risk model | Single-condition, requires clinical setting, no facility-capability routing |
| ARMMAN/mMitra | Mate A et al., "Field Study in Deploying Restless Bandits", AAAI 2022. DOI: 10.1609/aaai.v36i11.21460 | AI for maternal health in India | Predicts program dropout, not clinical risk; no facility routing |
| WHO SMART Guidelines DAK for ANC | WHO/RHR/21.1, 2021 | Digital ANC with referral | Rule-based guidelines, no computed risk scores, no spatial indexing |
| Niramai Health Analytix | Multiple Indian and international patents granted (incl. WO2017145125A1, US10307141B2) for AI thermal image analysis in breast cancer screening | Favorable Section 3(k) precedent | Different domain (breast cancer), demonstrates AI + physical measurement → clinical output is patentable in India |

### Competitor Landscape
| Competitor | What It Does | What It Lacks |
|-----------|-------------|---------------|
| ARMMAN/mMitra (61M women) | AI predicts program dropout (Google DeepMind RMAB) | No clinical risk scoring, no facility routing, no Hb prediction |
| ASHABot (Microsoft/Khushi Baby) | GPT-4 WhatsApp Q&A for ASHAs (869 workers, Udaipur) | Reactive only, no risk prediction, no routing |
| Kilkari (60M women, 27 states) | Broadcast IVR voice calls timed to gestational age | One-way, same messages for all, no risk assessment |
| CommCare (500K+ users, 80 countries) | Open-source CHW case management platform | No AI risk scoring, no facility-capability routing |
| OpenSRP (150M patients, 14 countries) | WHO Smart Guidelines digitization, FHIR-native | Digitizes guidelines, no predictive analytics |
| Safe Delivery App (300K+ workers) | Animated clinical instruction videos, offline | Training tool only, no patient data, no predictions |
| PIERS-ML (Lancet Digital Health 2024, DOI: 10.1016/S2589-7500(23)00267-4) | Random forest pre-eclampsia prediction (8,843 women) | Pre-eclampsia only, requires hospital labs, not community-level |
| Delfina ($17M raised) | ML for hypertension/GDM, US health plans | US-only, requires EHR, not for LMICs or CHWs |
| CareNX/Fetosense (500K+ screened) | AI portable fetal monitoring device | Requires proprietary hardware, hospital-level |

### Environmental & Sustainability
| Data Point | Source | Verification |
|-----------|--------|-------------|
| Cloud migration: up to 88% carbon reduction | 451 Research/AWS, "The Carbon Reduction Opportunity of Moving to Amazon Web Services", 2019 | aws.amazon.com/sustainability |
| Google Cloud PUE 1.09 vs industry 1.56 | Google Environmental Report 2024 | sustainability.google |
| ASHA register maintenance: 41 min/day | Kaur J et al., PMC 2023 time-motion study | PMC10746798 |
| DPDP Act 2023: penalties up to INR 250 crore | Digital Personal Data Protection Act, 2023. PRS India Legislative Brief | prsindia.org |

---

## Codebase-to-Claim Verification Matrix

This section maps every patent claim to verified source code, with exact file paths and data counts.

| Patent Claim | Code Location | Verified Value | Status |
|-------------|---------------|----------------|--------|
| 70,000 risk entries | `data/risk_table.json` (33 MB) | 70,000 keys | ✓ Exact |
| 7 clinical dimensions | `app/engines/risk_scoring.py` L24-30 | age, parity, Hb, BP, gest_wk, BMI, complications | ✓ Exact |
| Hash-based lookup | `app/engines/risk_scoring.py` L133-146 | SHA-256 → 16-char key → dict | ✓ Verified |
| Risk levels: Low<1%, Med 1-5%, High 5-15%, Crit≥15% | `app/engines/risk_scoring.py` L366-373 | Exact thresholds | ✓ Exact |
| Hb feedback re-scores risk with projected delivery Hb | `app/api/v1/routes.py` L210-232 | Re-score if predicted Hb < current | ✓ Implemented |
| Risk → capability mapping (EmOC) | `app/api/v1/routes.py` L240-248 | critical→comp_emoc, high→blood, med→basic | ✓ Implemented |
| Precomputed spatial index used for routing | `app/api/v1/routes.py` L253-262 | `_referral_engine.route()` called | ✓ Implemented |
| Blood bank CMS queried during assessment | `app/api/v1/routes.py` L266-274 | `_blood_bank.query_availability()` called | ✓ Implemented |
| DP applied to dashboard statistics | `app/api/v1/routes.py` L411-419 | `_dp_engine.privatize_stats()` called | ✓ Implemented |
| 10,602 geocoded facilities (exemplary) | `data/facility_graph.json` (106 MB) | 10,602 | ✓ Exact (as of build) |
| data.gov.in source | `app/precompute/generate_facility_graph.py` L21 | Resource 37670b6f | ✓ Verified |
| 46,013 precomputed grid cells (exemplary) | `data/facility_graph.json` SPT (basic_emoc) | 46,013 | ✓ Exact (as of build) |
| 5 capability levels | `app/models/enums.py` | basic/comp_emoc, blood, c_section, nicu | ✓ Verified |
| 2,497-parameter MLP | `data/learned_index_weights.json` | 2,497 | ✓ Exact (mathematically verified) |
| 5→64→32→1 architecture | `app/engines/learned_index.py` L35-41 | Linear(5,64)→ReLU→Linear(64,32)→ReLU→Linear(32,1) | ✓ Exact |
| 7,480 literature-derived profiles | `data/hb_trajectories.json` (7 MB) | 7,480 | ✓ Exact |
| 2,484 blood banks (exemplary) | `data/real_blood_banks.json` (436 KB) | 2,484 | ✓ Exact (as of build) |
| Count-Min Sketch (w=256, d=4) | `app/engines/blood_bank_sketch.py` L44, L96 | width=256, depth=4 | ✓ Verified |
| Differential Privacy (Laplace, ε=1.0) | `app/engines/differential_privacy.py` L57, L84-113 | epsilon=1.0 | ✓ Verified |
| Beta-Binomial Bayesian (in-memory) | `app/engines/bayesian_updater.py` L84-87 | Conjugate posterior | ✓ Verified |
| 12 Indian languages | `app/templates/index.html` L387-399 | 12 BCP-47 locale options | ✓ Verified |
| Scale-to-zero serverless | `infra/cloud_run.tf` + `infra/variables.tf` L30-34 | min_instances=0 | ✓ Verified |
| No database at runtime | `app/main.py` | All data from static JSON | ✓ Verified |
| RR values (8.0, 3.0, 15.0, etc.) | `app/engines/risk_scoring.py` L279-335 | All match | ✓ Exact |
| Temporal risk trajectory (Engine 1 ↔ 3 coupling) | `app/engines/temporal_risk.py` L51-178 | Week-by-week re-score with predicted Hb | ✓ Verified |

---

## Corrections Log (Claims Adjusted From Prior Drafts)

| # | Original Claim | Issue | Corrected To | Reason |
|---|---------------|-------|-------------|--------|
| 1 | "30,284 real geocoded facilities" | Only 10,602 had valid geocoordinates | "10,602 geocoded facilities in the exemplary embodiment" | Accurate count; "exemplary embodiment" acknowledges build-time variability |
| 2 | "60MB container" | Data alone is 154 MB | Removed specific size claim | Container image significantly exceeds 60 MB |
| 3 | "O(1)" for learned index | Requires bounded local search | "learned index MLP with bounded local search" | Precise algorithmic description |
| 4 | "$53/month for 10M assessments" | Depends on deployment config | "minimal compute cost" | Avoids unverifiable specifics |
| 5 | "offline-first design for 2G connectivity" | No PWA/service worker | "lightweight design for low-bandwidth connectivity" | Honest about current state |
| 6 | "WHO-calibrated profiles" | Model params from individual studies, not WHO | "literature-derived profiles with WHO anemia classification thresholds" | Prevents misrepresentation |
| 7 | Risk thresholds mismatched code | Code uses <1%/1-5%/5-15%/≥15% | Corrected to match code | Verified against `risk_scoring.py` L366-373 |
| 8 | Hypertensive crisis RR 15.0 attributed to Abalos | Code attributes to Say et al. | Corrected; Abalos attributed to Stage 2 HTN RR 5.0 | Citation consistency |
| 9 | Bayesian "enables regional calibration" | In-memory only, resets on restart | Added "in-memory; persistence planned" | Honest about implementation state |
| 10 | "IFA 70% anemia reduction" (ambiguous) | Could imply mortality reduction | "70% reduction in anemia prevalence at term" | Cochrane finding specificity |
| 11 | Sibai citation inconsistency | Code vs. document cited different papers | Standardized to Obstet Gynecol 2005 with DOI | Citation consistency |
| 12 | Engines isolated — no integration in `/assessment` | Google Places used instead of precomputed index; no Hb feedback; blood bank hardcoded | Rewrote `/assessment` endpoint with closed-loop pipeline | Integration now implemented in code |
| 13 | DP engine unused | Initialized but never applied | Applied to `/dashboard-stats` endpoint | DP now operational |
| 14 | Blood bank status hardcoded "available" | CMS never queried | CMS queried for blood_transfusion/comp_emoc referrals | Real probabilistic estimate |
| 15 | "Google Cloud Run" in claims | Vendor-specific | "Serverless compute platform with scale-to-zero" | Vendor-neutral claim language |
| 16 | Specific data counts as architectural constants | Build-time dependent | Prefixed with "in the exemplary embodiment" | Acknowledges variability |
| 17 | Voice interface claimed as inventive | Uses browser Web Speech API | Described as "user interface feature, not part of inventive architecture" | Honest scope |
| 18 | Market research citations unverifiable | No DOIs for paywall reports | Replaced with government sources (NHM, Union Budget, PIB) where possible | Verifiable citations |
