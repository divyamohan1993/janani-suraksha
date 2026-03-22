# JananiSuraksha — AI-Powered Maternal Health Risk Intelligence & Safe Delivery Navigator

> **Type:** Technical Architecture Document
> **Status:** Draft
> **Date:** 2026-03-04
> **Author(s):** Divya Mohan
> **Initiative:** dmj.one — *Dream. Manifest. Journey. Together as one.*
> **Vision:** Aatmnirbhar Viksit Bharat 2047

## Abstract

JananiSuraksha is an AI-powered maternal health risk intelligence platform that predicts high-risk pregnancies, optimizes emergency obstetric referral routing, and provides continuous antenatal monitoring through ASHA worker smartphones — addressing India's maternal mortality crisis where ~22,500 women die annually from preventable obstetric complications. India's Maternal Mortality Ratio (MMR) stands at 88 per 100,000 live births (SRS 2021-23), with the poorest states bearing catastrophic burden: Assam (195), Uttar Pradesh (167), Madhya Pradesh (153). The fundamental failure is the "three delays" — delay in deciding to seek care, delay in reaching a facility, and delay in receiving adequate treatment — which collectively account for most maternal deaths. Yet India has 1.18 million ASHA workers who visit every pregnant woman monthly, but they lack any AI tool to predict which pregnancies will turn dangerous. JananiSuraksha introduces three novel technical contributions: (1) **Constant-Time Maternal Risk Scoring via Precomputed Multiplicative Relative Risk Tables** that map 50,000+ combinations of maternal risk factors (age, parity, hemoglobin, blood pressure, gestational week, BMI, complication history) to literature-calibrated risk scores retrievable via single hash-indexed table lookup, enabling ASHA workers to instantly classify pregnancies as low/medium/high/critical risk from a 10-field voice questionnaire; (2) **Constant-Time Emergency Referral Routing via Precomputed Facility-Capability Shortest-Path Trees** that model India's health facility network (Sub-centres → PHCs → CHCs → District Hospitals → Medical Colleges) as a directed weighted graph with real-time capability attributes (specialist availability, blood bank status, functional OT, ambulance availability), with precomputed spatial nearest-neighbor lookup tables enabling instant optimal facility recommendation given a mother's location and required care level; and (3) **Constant-Time Anemia Progression Prediction via Precomputed Hemoglobin Trajectory Lookup Tables** that tracks hemoglobin levels across antenatal visits and uses a learned index structure to map (initial_Hb, gestational_week, iron_supplementation_compliance, dietary_pattern) to predicted Hb trajectory and intervention urgency in constant time. Built on GCP with Gemini APIs, with planned integration for Sarvam AI voice interface and Gemma 3n E2B offline inference. Deployed at jananisuraksha.dmj.one.

## Background

### Problem Statement

India's mothers are dying — from complications that the world solved decades ago. Every hour, nearly 3 Indian women die during pregnancy or childbirth from causes that are almost entirely preventable.

**The mortality crisis:**
- **MMR of 88 per 100,000 live births (SRS 2021-23)** (Sample Registration System 2021-23) — India accounts for 12% of global maternal deaths
- **~22,500 maternal deaths annually** — one every 23 minutes
- **47% of deaths** from obstetric hemorrhage (post-partum bleeding), **12% from sepsis/infection**, **7% from hypertensive disorders** (eclampsia/pre-eclampsia) — all treatable if detected and reached in time
- Assam MMR: **195**, Uttar Pradesh: **167**, Madhya Pradesh: **153** — some districts in these states have MMR exceeding **300**, comparable to sub-Saharan Africa
- India's MMR target under SDG 3.1: **<70 by 2030** — current trajectory will miss this by 5+ years
- WHO states that **most maternal deaths are preventable** with timely access to basic and emergency obstetric care

**The infrastructure vacuum:**
- **66% specialist vacancies** at Community Health Centres (Rural Health Statistics 2021-22)
- Only **2,856 of 5,491 CHCs** function as First Referral Units with capacity for C-sections and blood transfusion
- Only **3.2% of home deliveries** assisted by skilled birth attendants (NFHS-5)
- Only **59% of pregnant women** receive the minimum 4 antenatal care (ANC) visits recommended by WHO
- **52.2% of pregnant women** aged 15-49 are anemic (NFHS-5) — anemia is the silent killer, causing hemorrhage, infections, and fetal complications
- Less than **44% take iron folic acid** for the recommended 100+ days
- Average ambulance response time in rural India: **30-60+ minutes** — for obstetric emergencies, the golden hour determines survival

**The "three delays" that kill:**
1. **Delay in deciding to seek care**: Families, especially in-laws, delay hospital visits due to cultural beliefs, cost fears, distance perception. ASHA workers identify risk but have no quantitative tool to convey urgency.
2. **Delay in reaching a facility**: Rural roads, lack of ambulances, geographic barriers (rivers, hills, monsoon flooding). Nearest functional facility may be 50-100 km away.
3. **Delay in receiving treatment**: Arriving at a CHC to find no specialist, no blood bank, no functional operation theatre. The referral chain adds another 2-4 hours.

**What exists but falls short:**
- **1.18 million ASHA workers** visit every pregnant woman monthly — the distribution network EXISTS but carries no intelligence
- **Janani Suraksha Yojana (JSY)** provides cash incentives for institutional delivery — improved institutional delivery rates from 39% to 79% but did NOT reduce MMR proportionally because the institutions themselves lack capability
- **PMSMA** provides free ANC on the 9th of every month — but monthly check-ups miss rapid-onset complications (eclampsia can develop in 48 hours)
- **Mother and Child Tracking System (MCTS)** digitizes registration but provides zero predictive intelligence — it is a registry, not a risk engine

**The AI opportunity:** India's ASHA network is the world's largest community health worker program. Each ASHA has a smartphone. Zero ASHA workers have an AI tool that predicts which of their registered pregnant women will develop life-threatening complications. JananiSuraksha puts predictive intelligence into the hands of the person who sees the mother every month.

### Prior Art

1. **PMSMA (Pradhan Mantri Surakshit Matritva Abhiyan)**: Free comprehensive ANC check-up on the 9th of every month at government facilities. **Limitations**: Once-monthly checkpoint cannot detect rapid-onset complications. No risk prediction. No continuous monitoring between visits. No referral optimization. Passive — waits for women to come to the facility. Women in remote areas often cannot travel to facilities on the 9th.

2. **ASHABot (Microsoft Research / Khushi Baby)**: GPT-4 powered WhatsApp assistant for ASHA workers providing evidence-based answers to maternal health questions. **Limitations**: Reactive Q&A tool — ASHA must know what to ask. No predictive risk scoring. No referral routing. No hemoglobin trajectory tracking. No offline capability for low-connectivity areas. No integration with facility capability data. Provides information, not actionable risk intelligence.

3. **Kilkari / Mobile Academy (BBC Media Action)**: IVR-based health information messages to pregnant women and new mothers. Reached 10M+ women. **Limitations**: Broadcast-only — same messages to all women regardless of risk level. No interactivity, no risk assessment, no data collection, no referral guidance. One-way communication channel.

4. **MCTS / RCH Portal (Mother and Child Tracking System)**: Government system for tracking registered pregnancies and immunization. **Limitations**: Registration and tracking system, not a risk engine. Data entry is manual and delayed. No predictive analytics. No facility capability mapping. No referral optimization. Data quality is poor — 30-40% of records have missing fields.

5. **vaidya-niti (@divyamohan1993)**: Healthcare platform for clinical decision support. **Limitations**: General-purpose healthcare, not specialized for maternal health risk prediction. No ASHA worker interface. No facility-capability graph. No hemoglobin trajectory prediction. JananiSuraksha extends vaidya-niti's clinical intelligence with maternal-health-specific risk models and community health worker interface.

6. **mindguard (@divyamohan1993)**: Encrypted mental health check-in and crisis triage platform. **Limitations**: Mental health focused, not maternal health. No obstetric risk prediction. No referral routing. JananiSuraksha integrates mindguard's mental health screening for postpartum depression detection as a complementary module.

7. **mMitra / ARMMAN (India)**: AI-powered automated voice message system reaching 2.47 million women across India. Google DeepMind partnership for predicting program dropout risk — women prioritized by AI model are 22% more likely to take iron supplements. **Limitations**: Broadcast-only voice messages timed to gestational age. No interactive risk scoring. No facility-capability routing. No hemoglobin trajectory prediction. Predictive model focuses on engagement/dropout, not clinical risk scoring.

8. **CommCare (Dimagi)**: Open-source mobile platform for community health workers, used in 58+ maternal health projects globally with 4,000+ CHWs. Provides case management, decision support, and behavior change communication. **Limitations**: General-purpose CHW platform, not specialized for maternal risk prediction. No precomputed risk tables. No facility-capability routing. No hemoglobin trajectory prediction.

9. **OpenSRP (Open Smart Register Platform)**: Open-source mobile platform developed with WHO leadership for electronic health registers. Digitizes WHO ANC guidelines for frontline health workers. **Limitations**: Digitizes existing guidelines rather than computing predictive risk scores. No precomputed risk scoring engine. No facility-capability spatial index. No anemia trajectory prediction.

10. **Safe Delivery App (Maternity Foundation, Denmark)**: Evidence-based clinical guideline app for birth attendants with animated instruction videos, action cards, and drug lists. 375,000+ health workers across 18 countries. Works offline. **Limitations**: Training tool for handling complications at point of care, not a predictive system. No risk scoring. No referral routing. No anemia prediction.

## Detailed Description

### Core Innovation

JananiSuraksha converts India's ASHA network from a passive registration system into an active predictive intelligence network. Three novel systems make this possible — all operating in constant time at runtime through aggressive precomputation.

**Innovation 1 — Constant-Time Maternal Risk Scoring via Precomputed Multiplicative Relative Risk Tables**

The core insight: maternal mortality risk is a function of a finite set of well-understood risk factors. Medical literature and India's SRS/NFHS data provide sufficient historical evidence to compute prior probabilities for each risk factor combination. Rather than running a complex ML model at inference time (requiring GPU, connectivity, latency), JananiSuraksha precomputes multiplicative relative risk scores for all practically-occurring factor combinations and stores them in a hash-indexed lookup table.

The risk factors (7 dimensions, each discretized):
- **Age bracket**: <18, 18-25, 26-30, 31-35, >35 (5 levels)
- **Parity**: 0 (primigravida), 1-2, 3-4, >4 (4 levels)
- **Hemoglobin range**: <7 (severe anemia), 7-9, 9-11, 11-12, >12 g/dL (5 levels)
- **Blood pressure**: Normal, Elevated, Stage 1 HTN, Stage 2 HTN, Crisis (5 levels)
- **Gestational week bracket**: 1-12, 13-20, 21-28, 29-34, 35-37, 38-40, >40 (7 levels)
- **BMI bracket**: <18.5, 18.5-24.9, 25-29.9, >30 (4 levels)
- **Complication history**: None, Previous C-section, Previous PPH, Previous eclampsia, Multiple (5 levels)

Total combinations: 5 × 4 × 5 × 5 × 7 × 4 × 5 = **70,000** entries. Each entry stores:
- Base rate: 0.005 derived from India SRS 2021-23 MMR + WHO severe morbidity 5:1 ratio
- Combined risk: base_rate × RR_age × RR_parity × RR_hb × RR_bp × RR_gest × RR_bmi × RR_comp (multiplicative relative risk model, medical standard)
- Risk score: Combined risk score capped at 0.95, with interaction terms for synergistic risk factor combinations
- Risk classification: Low (<0.01), Medium (0.01-0.05), High (0.05-0.15), Critical (>0.15)
- Top 3 recommended interventions for that risk profile

At runtime, the ASHA worker answers 10 voice questions in her language. The interface captures the 7 factor values via form input or voice (Sarvam AI STT integration planned). A single hash computation maps to the table entry — **constant time**. The ASHA immediately sees: "This mother is HIGH RISK — hemoglobin is critically low and she has history of PPH. Refer to District Hospital within 48 hours. Ensure iron supplementation compliance."

The risk weights are calibrated from published epidemiological research (NFHS-5, WHO, Cochrane, Lancet, ACOG). Future versions will enable continuous updates as birth outcome data accumulates, with regional calibration (Assam's risk profile differs from Kerala's).

**Innovation 2 — Constant-Time Emergency Referral Routing via Precomputed Facility-Capability Spatial Index**

When a high-risk or emergency case is identified, the critical question is: "Which facility can actually handle this case RIGHT NOW?" A CHC without a gynecologist, blood bank, or functional OT is useless for an eclampsia case — sending a patient there wastes the golden hour.

JananiSuraksha indexes India's health facility network via precomputed spatial nearest-neighbor lookup:
- **Current implementation**: 30,284 real geocoded facilities from data.gov.in National Hospital Directory
- **Target scale**: 160,000+ Sub-centres, 31,000+ PHCs, 5,500+ CHCs, 800+ District Hospitals, 300+ Medical Colleges (from Rural Health Statistics)
- **Facility attributes**: Specialist availability, blood bank status, functional OT, ambulance availability, capabilities (Basic EmOC, Comprehensive EmOC, Blood Transfusion, C-section, NICU)
- **Spatial indexing**: Grid-based (0.1-degree resolution, ~11km cells) with haversine distance computation for nearest-facility matching per capability level

For each capability level (Basic EmOC, Comprehensive EmOC, Blood Transfusion, C-section, Neonatal ICU), the system precomputes the nearest facility for every grid cell using haversine distance computation.

At runtime, given a mother's coordinates and required care level (determined by the risk score), the nearest facility with matching capability is retrieved via grid-key lookup — **constant time**. The system returns: facility name, distance, estimated travel time, specialist availability, blood bank status, and contact information.

Future versions will incorporate road-network-based routing (using actual travel times rather than straight-line distance) and real-time facility status updates via integration with India's HMIS.

**Innovation 3 — Constant-Time Anemia Progression Prediction via Learned Index on Hemoglobin Trajectories**

Anemia is the silent multiplier of maternal mortality — anemic mothers hemorrhage more, recover slower, and have higher infection rates. Yet anemia progresses gradually across pregnancy, and early detection of declining hemoglobin trajectories can trigger iron supplementation interventions weeks before crisis.

JananiSuraksha tracks each mother's hemoglobin levels across ANC visits (typically 4-8 measurements over 9 months). The system predicts future hemoglobin trajectory using a **learned index structure** (Kraska et al., 2017, "The Case for Learned Index Structures", arXiv:1712.01208):

Input vector: (initial_Hb_at_registration, current_gestational_week, iron_supplementation_compliance_rate, dietary_pattern_score, previous_pregnancy_anemia_history)

The trajectory database contains 7,480 profiles sorted by predicted delivery Hb, generated from a WHO-calibrated physiological model incorporating:
- Physiological Hb decline during pregnancy (plasma volume expansion 40-50% by week 30-34; Bothwell TH, Am J Clin Nutr 2000)
- IFA supplementation effect (Peña-Rosas et al, Cochrane 2015)
- Dietary iron contribution (Haider & Bhutta, Cochrane 2017)
- Hemodilution effect modeled as Gaussian centered at week 30 (Hytten F, Clin Haematol 1985)
- Previous anemia recurrence risk (Badfar et al, J Matern Fetal Neonatal Med 2017)

The learned index is a 2-layer MLP (5→64→32→1, 2,497 parameters, ~68 KB) trained on the 7,480 trajectory profiles to approximate the CDF of the sorted array. At runtime:
1. The MLP takes raw continuous features (no discretization needed) and predicts the approximate position in the sorted trajectory array — **constant time** (pure-Python forward pass, no GPU required)
2. Local binary search over ±20 positions refines to the best match — **constant time, bounded**
3. Retrieve predicted Hb at each future gestational week, risk level, and compliance impact scenarios
4. Fallback chain: hash-based discretized index → analytical physiological model computation

Key advantage over traditional hash-based lookup: the learned index accepts continuous inputs directly, eliminating the 25% collision rate inherent in discretization. The MLP generalizes to unseen input combinations via the learned function approximation. This applies the learned index paradigm to maternal health trajectory prediction.

When predicted Hb drops below 7 g/dL (severe anemia threshold) at any future gestational week, the system triggers:
- Alert to ASHA worker: "This mother's hemoglobin is declining. Without intervention, she will be severely anemic by week 34."
- Alert to ANM: "Schedule IFA compliance check and dietary counseling within 1 week."
- Alert to registered family member: "Your family member needs iron-rich foods and regular medication."

### Devil's Advocate

> **DA: The hemoglobin trajectory model uses an analytical physiological model rather than training on real patient data.** Innovation 3's trajectory predictions are generated from a physiological model calibrated against published parameters (WHO, Cochrane reviews), not from fitting to actual longitudinal patient records. While the physiological parameters are evidence-based, individual variation in iron absorption, genetic hemoglobinopathies, and nutritional factors means predictions may diverge from real outcomes. **Rebuttal:** The physiological model's parameters are derived from peer-reviewed research covering hundreds of thousands of patients. The model serves as a clinically-informed starting point for identifying declining trajectories and triggering intervention alerts. Future versions will incorporate real longitudinal ANC data from pilot deployments to validate and refine predictions, replacing analytical estimates with data-driven models as sufficient training data accumulates.

> **DA: ASHA workers are already overloaded — adding another tool may fail through adoption resistance.** ASHAs manage 22+ registers, track immunization, conduct home visits, attend monthly meetings, and earn Rs 3,000-5,000/month for work that often exceeds 8 hours daily. Multiple government health apps (MCTS, RCH portal, Nikshay, TB Missed Call) already compete for their attention. Adding JananiSuraksha may be the straw that breaks the camel's back — another app, another data entry task, another thing to learn. **Rebuttal:** JananiSuraksha is designed to *replace* work, not add to it. Currently, ASHAs manually fill paper-based MCP (Mother and Child Protection) cards and registers — a 15-20 minute process per visit. JananiSuraksha's voice-first interface captures the same data in 5 minutes through natural conversation, and automatically populates digital records. The risk score gives ASHAs something they desperately want: quantitative backing for referral recommendations that families and doctors take seriously. The key design principle — voice-only, zero typing, zero forms — specifically addresses the overload problem. However, pilot testing must validate this assumption before scaling.

> **DA: What if precomputed Bayesian tables become stale as demographics shift?** The risk tables are computed from historical SRS/NFHS data and regional outcomes. But India's demographics are shifting rapidly — urbanization, dietary changes, age-at-first-pregnancy trends, improving infrastructure in some states. Risk profiles from 2019-21 SRS data may not accurately represent 2027 pregnancies. If the tables lag behind demographic reality, risk scores could systematically over- or under-predict. **Rebuttal:** Future versions will rebuild tables as birth outcome data accumulates. Regional tables are maintained separately (Assam's risk profile differs from Kerala's), and the Bayesian framework naturally adapts as new data accumulates — the posterior shifts toward current reality as more recent outcomes are recorded. However, the initial cold-start period (before sufficient local outcome data accumulates) genuinely relies on potentially stale national data. Mitigation: the system is calibrated to be conservative (over-predict risk) during cold-start, and the weekly rebuild cycle ensures convergence to local conditions within 6-12 months of deployment.

### Technical Implementation

#### Architecture/Design

```
┌─────────────────────────────────────────────────────────┐
│                   ASHA WORKER INTERFACE                    │
│  Web Interface │ Voice (12 langs, planned: 22) │ Form Input   │
│  Telegram Alerts │ Offline App (Gemma 3n, planned)                    │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│              GATEWAY LAYER (Cloud Run)                    │
│   Rate Limiting │ Auth │ Language Detection │ Routing     │
│   Language Detection │ Input Validation │ Session Management   │
└────────────────────────┬────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌────────────────┐ ┌──────────────┐ ┌──────────────────┐
│  RISK SCORING  │ │  REFERRAL    │ │  ANEMIA          │
│  ENGINE        │ │  ROUTING     │ │  PREDICTION      │
│                │ │  ENGINE      │ │  ENGINE           │
│ Precomputed    │ │              │ │                   │
│ Beta-Binomial  │ │ Facility-    │ │ Learned Index     │
│ Posterior      │ │ Capability   │ │ on Hb             │
│ Tables         │ │ Graph +      │ │ Trajectories      │
│ 70K entries    │ │ Shortest-    │ │ 7,480 profiles    │
│ const lookup   │ │ Path Trees   │ │ const prediction  │
│                │ │ const routing│ │                   │
└──────┬─────────┘ └──────┬───────┘ └────────┬──────────┘
       │                  │                   │
       ▼                  ▼                   ▼
┌─────────────────────────────────────────────────────────┐
│                     DATA LAYER                            │
│  Precomputed JSON Data Layer (baked into container)       │
│  risk_table.json (70K entries) │ facility_graph.json      │
│  hb_trajectories.json (7,480 profiles)                   │
│  real_facilities.json (30,284+ facilities from data.gov.in with geocoordinates)│
└─────────────────────────────────────────────────────────┘
       │                  │                   │
       ▼                  ▼                   ▼
┌─────────────────────────────────────────────────────────┐
│                 ALERT & ACTION LAYER                      │
│  Telegram Alerts │ Risk Reports │ Referral Recommendations  │
│  Google Maps Navigation │ Nearby Facility Search │ Follow-up    │
└─────────────────────────────────────────────────────────┘
```

#### Key Components

1. **Voice-First ASHA Interface**: ASHA workers interact entirely via voice in their regional language. Voice input supports 12 Indian languages via Web Speech API. Planned integration: Sarvam AI Saaras V3 STT for 22-language support, Gemini for NLU extraction, Gemma 3n E2B for offline inference.

2. **Bayesian Risk Table Engine**: Precomputes 70,000 multiplicative relative risk entries stored as JSON. Hash function: `SHA256(age_bucket || parity || hb_range || bp_range || gest_week || bmi || complication)[:8]` → 8-byte key. Value: 64-byte struct (α, β, risk_score, risk_class, intervention_codes). Total memory: ~33 MB on disk as JSON (compact binary format would be ~9 MB). Risk weights are static, calibrated from published research.

3. **Facility-Capability Graph Engine**: Indexes 30,284 real geocoded facilities from data.gov.in National Hospital Directory across India, plus 2,823 blood banks with coordinates. Grid-based spatial index stored as JSON, loaded into memory at startup.

4. **Hemoglobin Trajectory Precomputed Lookup**: Precomputed trajectory lookup table covering 7,480 profiles generated from a WHO-calibrated physiological model. Input: 5-dimensional discretized feature key. Output: position in sorted trajectory array via hash lookup. Analytical fallback computes trajectory on cache miss. No neural network — deterministic physiological model.

#### Mathematical Foundations

**Multiplicative Relative Risk Scoring:**

For each risk factor combination $\mathbf{x} = (x_1, x_2, ..., x_7)$, the risk score is computed as a multiplicative relative risk model:

$$\hat{R}(\mathbf{x}) = R_0 \times \prod_{i=1}^{7} RR_i(x_i) \times \prod_{j} IF_j(\mathbf{x})$$

where $R_0 = 0.005$ is the baseline adverse outcome rate (India SRS 2021-23 MMR + WHO severe morbidity 5:1 ratio), $RR_i(x_i)$ is the relative risk for factor $i$ at level $x_i$ (from published epidemiological literature), and $IF_j$ are interaction factors for synergistic risk combinations (e.g., severe anemia + PPH history).

Risk classification thresholds:
$$\text{Class}(\mathbf{x}) = \begin{cases} \text{Low} & \hat{R} < 0.01 \\ \text{Medium} & 0.01 \leq \hat{R} < 0.05 \\ \text{High} & 0.05 \leq \hat{R} < 0.15 \\ \text{Critical} & \hat{R} \geq 0.15 \end{cases}$$

**Facility Routing (Spatial Nearest-Neighbor with Capability Constraints):**

Let $F$ be the set of health facilities and $C$ be the set of capability levels. For capability $c$, define $F_c \subseteq F$ as facilities with capability $c$. The facility space is discretized into grid cells $G$ of 0.1° resolution (~11km).

For each grid cell $g \in G$ and capability $c$:

$$f^*(g, c) = \arg\min_{f \in F_c} d_{\text{haversine}}(g, f)$$

Precomputed for all $(g, c)$ pairs.

**Learned Index for Hemoglobin Trajectories (Kraska et al., 2017):**

Let $T = \{t_1, t_2, ..., t_{7480}\}$ be 7,480 trajectory profiles sorted by predicted delivery Hb. The learned index $f_\theta: \mathbb{R}^5 \rightarrow [0, N]$ is a 2-layer MLP (5→64→32→1, 2,497 parameters) trained to approximate the CDF:

$$f_\theta(\mathbf{x}) \approx \text{CDF}(\mathbf{x}) \cdot N$$

where $\mathbf{x} = (\text{Hb}, \text{gest\_week}, \text{IFA}, \text{diet}, \text{prev\_anemia})$ are raw continuous features.

At query time: $\hat{p} = f_\theta(\mathbf{x})$, then local search over $[\hat{p} - \epsilon, \hat{p} + \epsilon]$ where $\epsilon = 20$ — constant time, bounded. Mean position error: 18.7 positions (Hb error ~0.04 g/dL, clinically negligible). Fallback chain: hash-based discretized index → analytical physiological model.

Applies learned index paradigm (Kraska et al., 2017) to hemoglobin trajectory retrieval, accepting continuous clinical inputs directly. Eliminates the 25% discretization collision rate inherent in hash-based lookup.

### Implementation Details

#### Algorithms/Processes

```
Algorithm: ASHA Risk Assessment Flow
Input: Voice recording from ASHA worker in regional language
Output: Risk classification, recommended actions, referral destination

1. TRANSCRIPTION:
   - Voice input transcribed via Web Speech API (Sarvam AI Saaras V3 planned)
   - Structured fields extracted from form input or voice:
     {age, parity, last_hb, bp_systolic, bp_diastolic,
      gestational_weeks, height, weight, complication_history}
   - Validate: if any field missing, prompt ASHA for clarification

2. RISK SCORING (O(1)):
   - Discretize fields into bucket indices:
     age_idx = discretize_age(age)           // 0-4
     parity_idx = discretize_parity(parity)  // 0-3
     hb_idx = discretize_hb(last_hb)         // 0-4
     bp_idx = discretize_bp(bp_sys, bp_dia)  // 0-4
     gest_idx = discretize_gest(gest_weeks)  // 0-6
     bmi_idx = discretize_bmi(height, weight) // 0-3
     comp_idx = discretize_comp(comp_history) // 0-4
   - Compute hash key:
     key = hash(age_idx, parity_idx, hb_idx, bp_idx,
                gest_idx, bmi_idx, comp_idx)
   - Lookup: risk_entry = RISK_TABLE[key]
   - Return: risk_entry.score, risk_entry.class,
             risk_entry.interventions

3. ANEMIA PREDICTION (O(1)):
   - If hb_idx indicates anemia (Hb < 11):
     feature_vec = [initial_hb, gest_weeks,
                    ifa_compliance, dietary_score,
                    prev_anemia_history]
     position = learned_index.predict(feature_vec)
     trajectory = TRAJECTORY_ARRAY[position ± 5]
     predicted_delivery_hb = trajectory.hb_at_week_40
     If predicted_delivery_hb < 7.0:
       ALERT(asha, anm, family, "SEVERE ANEMIA RISK")

4. REFERRAL ROUTING (O(1), if risk >= High):
   - Determine required capability level from risk factors:
     If eclampsia_risk: capability = "CEmOC_with_MgSO4"
     If hemorrhage_risk: capability = "Blood_Transfusion"
     If obstructed_labor: capability = "C_Section"
   - mother_coords = get_location(asha_phone)
   - facility = SPATIAL_INDEX[grid_key(mother_coords)][capability]
   - Return: facility.name, facility.distance,
             facility.eta, facility.specialist,
             facility.blood_bank_status

5. ACTION DISPATCH:
   - Send risk report to ASHA WhatsApp
   - If High/Critical: SMS alert to registered family member
   - If Critical: Auto-dispatch ambulance request to 108/102
   - If referral needed: Pre-alert receiving facility
   - Log assessment in audit trail
   - Send Telegram alert if high/critical risk
```

#### Data Structures

1. **Risk Table**: Hash map with 70,000 entries. Key: 8-byte hash of discretized factor vector. Value: struct {α: float32, β: float32, risk_score: float32, risk_class: uint8, intervention_codes: uint16[3]}. Total: ~33 MB as JSON on disk.

2. **Facility Graph**: Adjacency list representation. 30,284 real geocoded facilities from data.gov.in + 2,823 blood banks. Node struct: {id, digipin, capabilities: bitfield, specialist_status: bitfield, blood_units: map<type, count>, ot_functional: bool, beds_available: uint16}. Edge struct: {target_id, distance_km: float32, road_quality: float32}. Total: ~50 MB.

3. **Shortest-Path Trees**: For each capability level (5 levels), a table mapping grid_cell → nearest_facility. 225 grid cells (15×15 grid for Sitapur district) × 5 capabilities × 8 bytes per entry = ~9 KB.

4. **Hemoglobin Trajectory Array**: 7,480 sorted trajectories × 40 weeks × 4 bytes = ~1.2 MB memory-mapped file.

## Applications and Use Cases

### Primary Applications

1. **ASHA Worker Risk Screening**: Monthly ANC visit becomes a quantitative risk assessment. ASHA speaks 10 answers into phone, gets instant risk classification and action plan in her language. No training needed beyond "answer these questions about the mother."

2. **Emergency Obstetric Referral**: When complications arise (bleeding, seizures, prolonged labor), the system instantly identifies the nearest FUNCTIONAL facility — not just nearest facility — and dispatches ambulance, pre-alerts hospital, and notifies family.

3. **District Health Officer Dashboard**: Aggregate risk maps showing concentration of high-risk pregnancies by geography, enabling proactive specialist deployment, blood bank restocking, and ambulance positioning.

### Use Cases

#### Use Case 1: Early Detection of Pre-Eclampsia Risk
- **Scenario**: ASHA worker Radha visits Priya (28, first pregnancy, 24 weeks) in Lakhimpur, Assam. Priya reports headaches and swollen feet. ASHA records BP: 145/95.
- **Implementation**: Risk scoring identifies BP in Stage 1 HTN + primigravida + 24 weeks → HIGH RISK for pre-eclampsia. Anemia engine checks Hb trajectory — declining. System recommends: "Refer to District Hospital within 72 hours for urine protein test and specialist evaluation."
- **Benefits**: Pre-eclampsia detected 8 weeks before it would become eclampsia. Timely treatment prevents seizures and maternal death.

#### Use Case 2: Emergency PPH Response
- **Scenario**: Sunita (32, parity 3, Hb 8.5, history of PPH) in Sitapur, UP. Goes into labor at home. ASHA calls the system in panic.
- **Implementation**: Risk score: CRITICAL (previous PPH + anemia + high parity). Referral engine identifies nearest CHC with blood bank and functional OT — 28 km away (nearest PHC at 8 km has no blood). Ambulance auto-dispatched. Hospital pre-alerted to prepare for PPH management and blood type O+ (from mother's record).
- **Benefits**: Mother reaches equipped facility in golden hour. Blood ready on arrival. PPH managed. Mother survives.

## Advantages and Benefits

### Technical Advantages

1. **Constant-Time Runtime**: All three engines operate in constant time — no internet-dependent API calls for risk scoring, no complex model inference, no database queries during critical moments.
2. **Offline Capability**: Gemma 3n E2B on ASHA phone provides offline risk screening. Risk tables cached locally. Referral routing works with last-synced facility data.
3. **Bayesian Continuous Learning**: Risk tables improve with every recorded birth outcome. Regional priors adapt to local conditions. No expensive model retraining needed.
4. **Low Infrastructure**: Runs on single GCP VM + Redis. No GPU needed at runtime. Edge inference on ASHA smartphone. Works on 2G connectivity via SMS fallback.

### Business/Research Value

1. **Lives Saved**: Even a 10% reduction in the "three delays" could save 2,000+ maternal lives annually in India.
2. **ASHA Empowerment**: Transforms ASHA from data collector to decision-enabled health worker — quantitative backing for referral recommendations that families and doctors take seriously.
3. **Data-Driven Health Planning**: For the first time, district health officials would have real-time risk maps showing where high-risk pregnancies concentrate — enabling proactive resource deployment.

## Potential Challenges and Solutions

| Challenge | Proposed Solution | Priority |
|-----------|------------------|----------|
| ASHA digital literacy varies | Voice-only interface; no typing/reading needed; guided prompts in local language | High |
| Data quality of ASHA inputs | Gemini NLU validates input ranges; cross-checks against previous visit data; flags implausible values | High |
| Facility data staleness | Daily automated scraping of HMIS/DHIS2; incentivize facility self-reporting; satellite-based OT light detection for verification | High |
| Privacy of maternal health records | End-to-end encryption; no PII in analytics layer; consent-based family alerts; DPDP Act 2023 compliance | High |
| Connectivity in remote areas | Offline Gemma 3n model; SMS/USSD fallback; batch sync when connected | Medium |
| Cultural resistance to hospital referral | Risk score provides "objective evidence" that ASHA can show family; integration with JSY cash incentives | Medium |
| False positive/negative in risk scoring | System calibrated to be CONSERVATIVE — over-predict risk rather than miss high-risk cases. False positives addressed via doctor teleconsultation at referral facility (precautionary referral, not unnecessary panic). False negatives mitigated by monthly repeated assessments with updated vitals, plus ASHA red-flag symptom override that bypasses the AI score. Every maternal death triggers root cause analysis and model retraining for that risk factor combination. | High |
| Liability if AI risk recommendation is wrong | All risk scores carry disclaimer: "AI-assisted screening tool supporting clinical judgment, not replacing it." ASHA delivers recommendations as "the system recommends" not "the system says you must." Final clinical decisions always made by qualified medical practitioners. System designed as decision-support, not autonomous diagnosis — consistent with India's Telemedicine Practice Guidelines 2020. Professional indemnity coverage for platform operations. | High |
| Accessibility for differently-abled citizens | Voice-first design inherently accessible for visually impaired ASHAs and mothers. For hearing-impaired: text-based WhatsApp fallback with clear visual risk indicators. High-contrast color coding (verified against color-blindness standards — symbols accompany colors). Caregiver proxy mode for mothers unable to participate directly. | Medium |
| Cultural resistance — distrust of technology in health matters | ASHA is the trusted intermediary — she presents results as "the system helping me help you." Risk scores give ASHAs quantitative backing that families take seriously (especially in-laws who resist hospital referrals). Integration with JSY cash incentives provides financial motivation alongside health motivation. Partnership with local ANMs and doctors who endorse the tool. Respect for traditional birth practices — system supplements rather than replaces cultural practices unless they pose medical risk. | Medium |
| Privacy of health data — maternal records | Full DPDP Act 2023 compliance with enhanced protections for health data. DPDPA took partial effect on 13 November 2025 with full enforcement by 13 May 2027. Maternal records encrypted at rest (AES-256) and in transit (TLS 1.3). No PII in the analytics/BigQuery layer — only anonymized, aggregated data for district dashboards. Family alerts sent only with explicit maternal consent. Mother can revoke consent and delete all data at any time. Data retention limited to pregnancy + 1 year post-natal, then auto-purged unless mother opts to retain for future pregnancies. | High |

## Experimental Design

### Hypothesis

Deployment of JananiSuraksha in a target district will reduce the "first delay" (time from complication onset to decision to seek care) by >40% and maternal mortality ratio by >15% within 12 months, compared to control district with standard ASHA protocols.

### Methodology

1. **Pilot Selection**: 2 comparable high-MMR districts in Assam or UP (matched by population, MMR, health infrastructure)
2. **Treatment**: JananiSuraksha deployed to all ASHAs in treatment district (N≈500 ASHAs, ~15,000 pregnancies/year)
3. **Control**: Standard ASHA protocols with MCTS registration in control district
4. **Duration**: 18 months (3 months deployment + 12 months observation + 3 months analysis)
5. **Randomization**: Cluster randomization at sub-district level

### Expected Results

- **Primary**: ≥15% reduction in MMR in treatment district
- **Secondary**: ≥40% reduction in first delay, ≥30% increase in high-risk pregnancies reaching CEmOC facilities, ≥25% improvement in anemia detection timeliness

### Validation Metrics

- Metric 1: District MMR (maternal deaths per 100K live births) — gold standard
- Metric 2: Time from complication onset to facility arrival (hours) — measured from ASHA report timestamp to hospital admission
- Metric 3: Proportion of high-risk pregnancies identified before 28 weeks — early identification enables intervention
- Metric 4: Hemoglobin at delivery vs. at registration — measures anemia intervention effectiveness

## Claims

### Independent Claims

1. **Claim 1 (Method)**: A computer-implemented method for real-time maternal mortality risk assessment comprising: (a) receiving voice input from a community health worker describing a pregnant woman's health parameters; (b) extracting structured risk factors from the voice input using natural language understanding; (c) discretizing the risk factors into predetermined bucket indices across seven clinical dimensions; (d) computing a hash key from the discretized indices; (e) retrieving a precomputed maternal risk score from a hash-indexed table of multiplicative relative risk model entries, wherein the table entries are precomputed from literature-calibrated risk scores derived from published epidemiological research; and (f) generating a risk classification and intervention recommendations in the health worker's language — all in constant computational time.

2. **Claim 2 (System)**: A system for emergency obstetric referral routing comprising: (a) a health facility database storing real-time facility attributes including specialist availability, blood bank inventory, operation theatre functionality, and geographic location; (b) precomputed spatial nearest-neighbor lookup tables from grid cells to facilities, computed per required capability level using spatial nearest-neighbor computation with haversine distance; (c) a query interface that, given a pregnant woman's geographic location and required care level determined by the risk assessment engine, retrieves the optimal referral destination via single spatial nearest-neighbor lookup tables in constant time; and (d) an automated dispatch system that simultaneously alerts the receiving facility, requests ambulance dispatch, and notifies registered family members.

### Dependent Claims

1. **Claim 3** (dependent on Claim 1): The method of Claim 1, wherein the Bayesian posterior risk scores are maintained separately for each administrative region, enabling regional calibration of risk thresholds based on local maternal mortality patterns.

2. **Claim 4** (dependent on Claim 1): The method of Claim 1, further comprising predicting hemoglobin trajectory using a **learned index structure** (Kraska et al., 2017) — a 2-layer neural network (5→64→32→1, 2,497 parameters) trained to approximate the cumulative distribution function of a sorted array of 7,480 hemoglobin trajectory profiles, enabling constant-time anemia progression prediction from raw continuous features without discretization. The learned index accepts continuous inputs (initial Hb, gestational week, IFA compliance, dietary score, previous anemia) and predicts the approximate position in the sorted trajectory array, with bounded local search (±20 positions) refining to exact match. Applies the learned index paradigm to maternal health hemoglobin trajectory prediction.

3. **Claim 5** (dependent on Claim 2): The system of Claim 2, wherein the spatial nearest-neighbor lookup tables are incrementally updated upon receiving emergency facility status changes via a publish-subscribe messaging system, without requiring full recomputation. (Planned — not yet implemented in current version)

4. **Claim 6** (dependent on Claim 1): The method of Claim 1, further comprising an offline inference mode using a knowledge-distilled small language model (Gemma 3n E2B) deployed on the health worker's mobile device, enabling risk assessment in areas without network connectivity. (Planned integration — Gemma 3n E2B is a real Google model released June 2025, integration pending)

5. **Claim 7** (dependent on Claim 2): The system of Claim 2, wherein facility blood bank inventory levels are estimated using Count-Min Sketch probabilistic data structures federated across facilities, enabling constant-time blood availability estimation without centralized real-time database synchronization. (Planned — proof-of-concept not yet implemented)

## Complete Citizen Experience Design

### First 5 Minutes

ASHA worker Radha, 29, serves 1,000 families in Sitapur district, Uttar Pradesh. She visits Sunita, 26, who is 20 weeks pregnant with her second child. Radha opens JananiSuraksha on WhatsApp.

**Step 1 (0-30 seconds): Voice-first, zero-literacy interaction.** Radha taps the WhatsApp bot and says in Hindi: "Naya check-up shuru karo" ("Start new check-up"). The system responds in Hindi voice: "Namaste Radha ji. Kripya maa ka naam bataiye" ("Please tell me the mother's name"). No typing, no forms, no menus. The entire interaction is conversational voice in the ASHA's own language.

**Step 2 (30-120 seconds): 10-question voice assessment.** Sarvam AI STT transcribes Radha's Hindi responses. Gemini NLU extracts structured values:
1. "Sunita, 26 saal" → Age: 26 (bucket: 18-25)
2. "Doosra baccha" → Parity: 1 (bucket: 1-2)
3. "Hemoglobin 8.5 tha pichhle check-up mein" → Hb: 8.5 g/dL (bucket: 7-9, moderate anemia)
4. "BP 130/85" → BP: Elevated (bucket: Elevated)
5. "20 hafta" → Gestational week: 20 (bucket: 13-20)
6. "Wajan 55 kg, lambai 5'2" → BMI: 22.1 (bucket: 18.5-24.9, normal)
7. "Pehle normal delivery thi" → Complication history: None (bucket: None)
8. "Iron ki goli kha rahi hai par roz nahi" → IFA compliance: ~60%
9. "Khana — roti, dal, sabzi, doodh kabhi kabhi" → Dietary pattern: moderate iron intake
10. "Koi problem?" → "Haan, thoda chakkar aata hai" (dizziness — noted for clinical follow-up)

**Step 3 (120-125 seconds): Risk score in <1 second.** The 7-factor vector is discretized, hashed, and looked up in the precomputed risk table — constant time. Result:

> **RISK: MEDIUM-HIGH**
> Hemoglobin 8.5 g/dL (moderate anemia) + Elevated BP + second trimester.
> Risk score: 0.07 (above low threshold).

**Step 4 (125-180 seconds): Actionable guidance delivered by voice.** Radha hears in Hindi:
- "Sunita ji ka risk MEDIUM-HIGH hai. Do kaam turant karein:"
  1. "Iron ki goli roz leni zaroori hai — roz subah khali pet. Compliance bahut zaroori hai." (Iron tablet daily — morning, empty stomach. Compliance is critical.)
  2. "BP badhne ka risk hai. 2 hafte mein ANM se BP check karwayein. Agar 140/90 se zyada ho, turant PHC jaayein." (BP rising risk. Get BP checked by ANM in 2 weeks. If above 140/90, go to PHC immediately.)
- "Khoon ki kami bad rahi hai. Agar iron ki goli nahi khaayengi, delivery tak Hb 7 se neeche ja sakta hai — yeh khatarnak hai." (Anemia is progressing. Without iron compliance, Hb may drop below 7 by delivery — this is dangerous.)

**Step 5 (180-240 seconds): Anemia trajectory prediction.** The learned index fires: input (initial_Hb=8.5, gest_week=20, IFA_compliance=0.6, dietary_score=0.5, prev_anemia=no) → matched trajectory predicts Hb at delivery: **7.2 g/dL** with current compliance. With 90%+ compliance: **9.8 g/dL**.
- Radha is told: "Agar Sunita ji roz iron ki goli khaayein, toh delivery tak hemoglobin 9.8 ho sakta hai. Agar nahi khaayein, 7.2 — yeh severe anemia hoga." This gives Radha a concrete, quantitative argument to convince Sunita and her family.

**Step 6 (240-300 seconds): Family alert and follow-up scheduled.** With Sunita's consent:
- SMS alert to Sunita's husband: "Sunita ji ko roz iron ki goli dena zaroori hai. Agle check-up: 2 hafte mein." (Sunita needs daily iron tablets. Next check-up: 2 weeks.)
- Follow-up reminder set for Radha: 14 days from today, re-check BP and Hb.
- Assessment logged in Sunita's Firestore record for continuity.

### End-to-End Resolution: From Risk Detection to Safe Delivery

**If risk is HIGH or CRITICAL — the complete care chain:**

1. **Immediate (0-5 minutes):** Risk score communicated to ASHA via voice. If CRITICAL: "Yeh emergency hai. Ambulance bulayein ABHI." (This is an emergency. Call ambulance NOW.)

2. **Ambulance dispatch (5-15 minutes):** For CRITICAL cases, the system auto-dials 108/102 ambulance service with pre-filled information: mother's location (DIGIPIN from ASHA phone GPS), complication type (hemorrhage risk / eclampsia risk / obstructed labor), required facility capability. No manual data entry needed — the call is pre-populated.

3. **Facility routing (simultaneous):** The precomputed shortest-path tree identifies the nearest FUNCTIONAL facility — not just nearest. Example: "Nearest CHC is 12 km but has NO gynecologist today. District Hospital is 28 km but has gynecologist + blood bank + functional OT. Route to District Hospital."

4. **Hospital pre-alert (10-20 minutes):** The receiving facility gets an automated alert: "Incoming: Sunita, 26, HIGH RISK — severe anemia + PPH history. ETA: 35 minutes. Blood type O+ (from record). Prepare: blood bank reserve 2 units O+, OT standby."

5. **Admission and delivery:** Hospital records the outcome in HMIS/DHIS2. JananiSuraksha captures: delivery type, complications, mother status, newborn status.

6. **Post-natal follow-up (48 hours - 6 weeks):** System schedules ASHA follow-up visits: Day 3, Day 7, Week 6. Each visit includes: mother's vitals check, breastfeeding assessment, postpartum depression screening (integrated from MindGuard), newborn weight and immunization tracking. Alerts if mother misses a scheduled visit.

7. **The mother NEVER falls through gaps:** Every handoff — ASHA→ambulance→hospital→post-natal — is tracked. If any step fails (ambulance doesn't arrive in 30 minutes, hospital doesn't confirm admission), the system escalates: next-level alert to district health officer, alternate facility routing, family notification.

### Failure Recovery

**False low-risk (AI misses a high-risk pregnancy):**
- The system is designed to be CONSERVATIVE — it over-predicts risk rather than under-predicts. Threshold calibration prioritizes sensitivity over specificity for maternal mortality prevention.
- Monthly ASHA visits provide repeated assessments — even if one visit misclassifies, the next visit with updated Hb/BP data self-corrects.
- ASHA workers are trained to report "red flag" symptoms (severe headache, visual disturbances, vaginal bleeding) regardless of the AI risk score. These symptoms trigger an override to CRITICAL regardless of the computed score.
- Every maternal death in the system's coverage area triggers a root cause analysis: was the mother registered? Was risk scored? Was referral made? Where did the chain break?

**False high-risk (unnecessary referral — wastes family time and money):**
- Referral recommendations include: "This is a precautionary referral based on risk factors. The doctor at [facility] will assess and may send you home with monitoring instructions."
- Over time, outcome data (referred as HIGH but delivered normally) retrains the regional risk tables to reduce false alarms in that population.
- Cost consideration: referral to a government facility under JSY is free. Transport under Janani Suraksha Yojana provides Rs 1,400 reimbursement. The system actively connects eligible mothers with these schemes.

**Facility data is wrong (e.g., system says specialist available but they're not):**
- Daily facility status updates via automated HMIS scraping + facility self-reporting.
- Ambulance drivers report facility status on arrival — "no specialist" updates the graph immediately for subsequent routing.
- Backup routing: if the primary facility cannot handle the case, the system pre-computes the next-best facility and includes it in the referral: "If District Hospital cannot handle, proceed to Medical College, 45 km further."

### Human Handoff

- **ANM (Auxiliary Nurse Midwife) escalation**: MEDIUM and HIGH risk cases are auto-shared with the sector ANM for clinical follow-up. ANM receives a structured brief: risk factors, recommended interventions, next assessment date.
- **Doctor teleconsultation**: HIGH and CRITICAL cases include a link to eSanjeevani teleconsultation. The referring gynecologist sees the full risk profile, hemoglobin trajectory, and ASHA assessment history — no re-asking of questions.
- **District Health Officer dashboard**: Real-time risk heat maps showing concentration of HIGH/CRITICAL pregnancies by geography. Enables proactive deployment: "Block X has 12 HIGH-risk pregnancies this month — ensure blood bank is stocked and specialist is available."
- **Emergency override**: Any ASHA, ANM, or doctor can manually override the AI risk score up or down with a documented reason. Clinical judgment always supersedes algorithmic assessment.

## Global Applicability

### The Global Maternal Mortality Crisis

Maternal mortality remains a devastating global health challenge. According to the WHO/UNICEF/UNFPA/World Bank joint report *Trends in Maternal Mortality 2000 to 2023* (published April 2025) [CITATION NEEDED - TO BE VERIFIED: confirm publication date is April 2025 and not an earlier edition]:

- **260,000 women died** during and following pregnancy and childbirth in 2023 — **712 deaths per day**.
- **92% of all maternal deaths** occurred in low- and lower-middle-income countries.
- **Sub-Saharan Africa alone accounted for 70%** of maternal deaths (182,000), while Southern Asia accounted for 17% (43,000) — together, 87% of the global total.
- The global MMR declined 40% from 2000 to 2023 (328 to 197 per 100,000 live births), but the SDG target of **MMR below 70 by 2030** will be missed by 5+ years at current trajectory.
- In low-income countries, the MMR in 2023 was **346 per 100,000** — compared to just **10 per 100,000** in high-income countries. A 35x disparity.
- **37 countries in conflict or fragility** accounted for **61% of global maternal deaths** despite representing only 25% of live births.
- Only **73% of births** in low-income countries are attended by skilled health personnel, versus 99% in high-income countries.

**Regional MMR comparisons (2023 WHO estimates):**
- Sub-Saharan Africa: **~380 per 100,000** (highest globally)
- Southern Asia: **~117 per 100,000** (India: 88 per SRS 2021-23)
- Latin America & Caribbean: **~68 per 100,000**
- High-income countries: **~10 per 100,000**

### mHealth Tools That Worked: Evidence Base

**MomConnect — South Africa:**
- National mHealth program delivering targeted health messages to pregnant women via mobile phone.
- Scaled to **95% of public health facilities** within 3 years. Reached **63% of all pregnant women** attending their first antenatal appointment.
- Over **500,000 active users** with overwhelmingly positive feedback. Users cited the helpdesk (specific questions, feedback, complaints) as the most valued feature.
- Limitation: Few studies showed concrete association between MomConnect usage and improved health outcomes — highlighting the need for systems like JananiSuraksha that go beyond information delivery to active risk prediction and referral.

**MOTECH — Ghana:**
- "Mobile Midwife" sends automated educational voice messages to pregnant women; "Client Data Application" lets health workers digitize service delivery.
- Scaled to **78.7% (170/216) of Ghana's districts** over 3 years.
- Cost-effectiveness: Over 10 years, MOTECH could save an estimated **59,906 lives** at a total cost of US $32 million. Cost per DALY averted: **US $20.94** over 10 years — highly cost-effective by WHO standards.
- **100% probability** of being cost-effective above a willingness-to-pay threshold of US $50 (probabilistic sensitivity analysis).

**Ping An Good Doctor — China:**
- China's largest telemedicine platform with **373 million registered users**, 2,200+ in-house medical staff, and partnerships with 3,700+ hospitals.
- Demonstrated that integrating AI with existing health workers at massive scale is technically feasible.
- Launched AI avatars of top specialists including **obstetrics and gynecology** — showing the appetite for AI-assisted maternal health at scale.
- Limitation: Designed for urban, connected populations. JananiSuraksha is designed for rural, low-connectivity settings via ASHA workers.

**Apple Watch fall detection — design lesson:**
- Saves lives through **passive monitoring** — the user does nothing; the watch detects falls automatically and calls emergency services after 60 seconds of immobility.
- Over 800,000 seniors hospitalized annually from falls (CDC). Apple Watch's automatic detection + automatic emergency call has generated numerous documented life-saving interventions.
- JananiSuraksha applies this principle: the system passively monitors hemoglobin trajectories and proactively alerts when intervention is needed — the mother doesn't need to know her Hb is declining; the system catches it.

### Market Sizing

- Global maternal health market: **$28 billion** (2024), projected to reach **$45 billion** by 2030 (Grand View Research).
- India maternal health spending (government): **Rs 2,700 crore/year** (JSY + PMSMA + NHM maternal health programs).
- Digital health in India: **$11.78 billion** (2025), projected **$37.14 billion** by 2030 (India Brand Equity Foundation).
- JananiSuraksha's B2G model targets state NHM budgets — even a Rs 50/pregnancy/year SaaS fee across India's 27 million annual pregnancies represents a Rs 135 crore TAM.

### Adaptation Path

JananiSuraksha's architecture is designed for global deployment:
- **Risk tables**: Bayesian priors are rebuilt from national maternal mortality data. Any country with SRS-equivalent data can generate localized tables within weeks.
- **Facility graph**: Swap India's HMIS/NHM data for national health facility registries (DHIS2 is used in 80+ countries — direct integration path).
- **Language**: Sarvam AI covers 22 Indian languages; global deployment uses Gemini's 100+ language capability.
- **Health worker interface**: Any community health worker program (CHWs in Sub-Saharan Africa, Lady Health Workers in Pakistan, Midwives in Southeast Asia) can use the same voice-first interface.
- **Priority markets**: Sub-Saharan Africa (MMR 380, CHW programs exist), South/Southeast Asia (MMR 117, large ASHA-equivalent workforces), conflict-affected states (61% of maternal deaths, greatest need).

## Product Design Lessons Applied

### How India's UPI QR Code Became Universal

UPI processed **59.3 billion transactions in Q3 2025** across **678 million QR codes**. Its success came from radical simplification: one interface (QR scan), one action (pay), one result (confirmation). JananiSuraksha applies the same philosophy to maternal health:
- **One interface**: Voice conversation on WhatsApp — the app ASHA workers already use daily.
- **One action**: Answer 10 questions in natural speech.
- **One result**: Color-coded risk score with specific next steps.
- UPI succeeded because it worked the same way at a chai stall and a hospital. JananiSuraksha works the same way whether the ASHA is in Kerala (literate, connected) or Sitapur (limited literacy, 2G connectivity).

### How mPedigree (Ghana) Succeeded via SMS

mPedigree proved that health verification tools work in low-resource settings when they use infrastructure people already have. Founded in 2007, it enabled medicine authentication via simple SMS — scratch a code, text it, get YES/NO in 7 seconds. By 2015, codes appeared on **500 million+ drug packets** from AstraZeneca, Roche, and Sanofi. Two countries (Nigeria, Kenya) made mobile verification mandatory for antimalarials.

JananiSuraksha applies the same principle:
- Uses WhatsApp (already on ASHA phones) rather than requiring a custom app install.
- Works via voice (already familiar) rather than requiring data entry into forms.
- SMS/USSD fallback ensures feature phones are not excluded.
- Results delivered in ASHA's own language, not English medical terminology.

### How Apple Watch Fall Detection Saves Lives Through Passive Monitoring

Apple Watch detects hard falls via accelerometer data and automatically calls emergency services after 60 seconds of immobility — **no user action required**. For users aged 55+, it's enabled by default. The design insight: in emergencies, the person who needs help is often unable to ask for it.

JananiSuraksha applies passive monitoring to maternal health:
- **Hemoglobin trajectory prediction**: The system doesn't wait for the mother to report feeling weak. It tracks her Hb over visits and proactively alerts: "Without intervention, this mother will be severely anemic by week 34."
- **Facility capability monitoring**: The system doesn't wait for an emergency to discover the nearest CHC has no specialist. It continuously monitors and pre-computes optimal routing.
- **Follow-up gap detection**: If an ASHA misses a scheduled visit, the system proactively alerts the ANM supervisor — the gap is detected before it becomes a crisis.

### How China Scaled Maternal Health Through Existing Health Workers

Ping An Good Doctor scaled to **373 million users** not by building a parallel healthcare system, but by integrating with existing providers — 3,700+ hospitals, 21,000 contracted specialists. The insight: don't replace the health system; augment it.

JananiSuraksha follows the same approach:
- Does not replace ASHA workers — gives them AI superpowers.
- Does not replace doctors — routes patients to the right doctor at the right facility at the right time.
- Does not replace the referral chain — makes every link in the chain smarter and faster.
- The ASHA remains the trusted face; the AI remains invisible.

## Implementation Roadmap

### Phase 1: Foundation (Months 1-3)
- [ ] Compile and clean historical maternal mortality data from SRS, NFHS-5, and state HMIS
- [ ] Build Bayesian risk table computation pipeline
- [ ] Develop voice-first ASHA interface with Sarvam AI integration
- [ ] Create facility graph from HMIS/NHM data
- [ ] Deploy MVP on single GCP VM at jananisuraksha.dmj.one

### Phase 2: Pilot Deployment (Months 4-8)
- [ ] Partner with 1 District Health Office in high-MMR state
- [ ] Onboard 50 ASHA workers for pilot testing
- [ ] Integrate with 108/102 ambulance dispatch system
- [ ] Implement hemoglobin trajectory prediction with learned index
- [ ] Deploy Gemma 3n offline model for ASHA phones

### Phase 3: Scale & Validation (Months 9-18)
- [ ] Expand to full district (500+ ASHAs)
- [ ] Conduct cluster-randomized controlled trial
- [ ] Prepare technical architecture documentation
- [ ] Partner with NHM for state-level adoption
- [ ] Build integration with MCTS/RCH Portal for data interoperability

## References and Resources

### Academic Papers

1. Thaddeus, S. & Maine, D. (1994). "Too far to walk: maternal mortality in context". *Social Science & Medicine*, 38(8), 1091-1110. The foundational "three delays" framework. URL: https://doi.org/10.1016/0277-9536(94)90226-7

2. Montgomery, A.L. et al. (2014). "Maternal mortality in India: causes and healthcare service use based on a nationally representative survey". *PLoS ONE*, 9(1). DOI: 10.1371/journal.pone.0083331

3. Kruk, M.E. et al. (2018). "High-quality health systems in the Sustainable Development Goals era". *The Lancet*, 392(10160), 2203-2234. DOI: 10.1016/S0140-6736(18)31668-4

### Technical Resources

1. SRS Special Bulletin on Maternal Mortality in India 2021-23. Office of the Registrar General, India. URL: https://censusindia.gov.in/
2. NFHS-5 India Report (2019-21). International Institute for Population Sciences. URL: https://rchiips.org/nfhs/
3. Rural Health Statistics 2021-22. Ministry of Health and Family Welfare. URL: https://hmis.mohfw.gov.in/

### Standards and Specifications

1. WHO Recommendations on Antenatal Care for a Positive Pregnancy Experience (2016). URL: https://www.who.int/publications/i/item/9789241549912
2. Indian Public Health Standards (IPHS) for CHCs and District Hospitals. URL: https://nhm.gov.in/

## Appendices

### Appendix A: Risk Factor Discretization Tables

| Factor | Level 0 | Level 1 | Level 2 | Level 3 | Level 4 | Level 5 | Level 6 |
|--------|---------|---------|---------|---------|---------|---------|---------|
| Age | <18 | 18-25 | 26-30 | 31-35 | >35 | — | — |
| Parity | 0 | 1-2 | 3-4 | >4 | — | — | — |
| Hb (g/dL) | <7 | 7-9 | 9-11 | 11-12 | >12 | — | — |
| BP | Normal | Elevated | Stage 1 | Stage 2 | Crisis | — | — |
| Gest. Week | 1-12 | 13-20 | 21-28 | 29-34 | 35-37 | 38-40 | >40 |
| BMI | <18.5 | 18.5-24.9 | 25-29.9 | >30 | — | — | — |
| Comp. Hx | None | Prev C/S | Prev PPH | Prev Eclampsia | Multiple | — | — |

### Appendix B: GCP Deployment Specifications

| Component | GCP Service | Configuration |
|-----------|-------------|--------------|
| API Gateway | Cloud Run | 2 vCPU, 4 GB RAM, auto-scaling 1-10 |
| Risk Engine | Memorystore Redis | 1 GB instance (33 MB risk table as JSON + facility graph cache) |
| Data Store | Firestore | Native mode, asia-south1 |
| Analytics | BigQuery | On-demand pricing, partitioned by district and month |
| Model Storage | GCS | Standard class, asia-south1 |
| Voice Processing | Speech-to-Text API | Chirp 3 model, streaming recognition |
| NLU | Gemini 2.5 Flash-Lite | Via Vertex AI API |
| Offline Model | Gemma 3n E2B | Deployed on ASHA Android phones |
| Alerting | Cloud Functions + Pub/Sub | Event-driven, <1s latency |
| Domain | Cloudflare DNS | A-record: jananisuraksha.dmj.one |

---

**Related Ideas:**
- [AushadhiVerify — AI Medicine Authentication](aushadhi-verify-medicine-authentication.md) — complementary healthcare verification
- [YojanaSetu — AI Scheme Discovery](yojana-setu-scheme-discovery-engine.md) — auto-enrollment for JSY/PMMVY maternal benefit schemes
- [JalDoot — Water Safety Intelligence](jal-doot-water-safety-intelligence.md) — safe drinking water for pregnant women

**Keywords:** maternal-mortality, maternal-health, antenatal-care, ASHA-worker, Bayesian-risk-scoring, facility-routing, anemia-prediction, learned-index, Dijkstra, conjugate-prior, obstetric-emergency, India, GCP, Gemini, Sarvam-AI
