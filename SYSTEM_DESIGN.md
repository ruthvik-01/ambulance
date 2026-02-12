# 🚑 AI-Powered Real-Time Hospital Readiness & Smart Ambulance Routing System

## System Design Document

---

## 1. System Architecture (High-Level Components)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐     │
│  │  SOS Mobile   │  │  Dispatcher  │  │  Hospital Dashboard   │     │
│  │  Web App      │  │  Dashboard   │  │  (Bed/Status Mgmt)    │     │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬────────────┘     │
└─────────┼─────────────────┼─────────────────────┼──────────────────┘
          │                 │                     │
          ▼                 ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      API GATEWAY / BACKEND                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                   Flask REST API Server                       │   │
│  │                                                              │   │
│  │  ┌────────────┐ ┌────────────┐ ┌──────────────────────────┐ │   │
│  │  │ SOS Handler│ │ Hospital   │ │  Ambulance Route Engine  │ │   │
│  │  │ & Triage   │ │ Matcher    │ │  (Traffic-aware)         │ │   │
│  │  └────────────┘ └────────────┘ └──────────────────────────┘ │   │
│  │                                                              │   │
│  │  ┌────────────────────────┐ ┌─────────────────────────────┐ │   │
│  │  │  Hospital Readiness    │ │  Pre-Alert Notification     │ │   │
│  │  │  Scoring Engine (AI)   │ │  Service                    │ │   │
│  │  └────────────────────────┘ └─────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
          │                 │                     │
          ▼                 ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       DATA & SERVICES LAYER                         │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐     │
│  │  Hospital DB  │  │  Google Maps │  │  AI/ML Prediction     │     │
│  │  (SQLite /    │  │  Directions  │  │  Module               │     │
│  │   JSON mock)  │  │  & Traffic   │  │  (Readiness Forecast) │     │
│  └──────────────┘  └──────────────┘  └───────────────────────┘     │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐                                │
│  │  WebSocket    │  │  SMS/Push    │                                │
│  │  Real-time    │  │  Alert       │                                │
│  │  Updates      │  │  Service     │                                │
│  └──────────────┘  └──────────────┘                                │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Breakdown

| Component                  | Role                                                           |
| -------------------------- | -------------------------------------------------------------- |
| **SOS Mobile Web App**     | One-tap emergency trigger, captures GPS, optional patient info |
| **Dispatcher Dashboard**   | Ambulance operators see live status, override AI decisions     |
| **Hospital Dashboard**     | Hospitals update bed/staff/equipment availability in real-time |
| **SOS Handler & Triage**   | Receives emergency, classifies severity & type                 |
| **Hospital Matcher**       | Filters hospitals by specialization + proximity                |
| **Readiness Scoring (AI)** | Calculates composite score per hospital                        |
| **Route Engine**           | Computes fastest route with live traffic                       |
| **Pre-Alert Service**      | Notifies selected hospital with ETA + patient type             |
| **Hospital DB**            | Stores hospital profiles, beds, specializations, history       |
| **AI/ML Prediction**       | Predicts bed availability at future arrival time               |

---

## 2. Detailed Workflow: Emergency Trigger → Hospital Arrival

```
STEP 1: EMERGENCY TRIGGER
──────────────────────────
User opens app → Taps "SOS" button
  → GPS location captured automatically
  → Optional: Select emergency type (Trauma / Cardiac / Burns / General)
  → Optional: Add notes (conscious? breathing?)
  → Request sent to backend

STEP 2: TRIAGE & CLASSIFICATION
────────────────────────────────
Backend receives SOS with:
  { location: [lat, lng], type: "cardiac", severity: "high", timestamp }
  → Emergency type mapped to required facilities:
      cardiac → needs: ["ICU", "Cath Lab", "Cardiologist"]
      trauma  → needs: ["ICU", "Trauma Center", "Surgeon"]
      burns   → needs: ["Burns Unit", "ICU", "Plastic Surgeon"]
      general → needs: ["Emergency Ward", "General Doctor"]

STEP 3: HOSPITAL DISCOVERY
───────────────────────────
  → Query database for hospitals within configurable radius (default: 15km)
  → Fetch each hospital's current status:
      - Available ICU beds
      - Available specialists on duty
      - Equipment availability
      - Current patient load (%)

STEP 4: READINESS SCORING (Core AI Logic)
──────────────────────────────────────────
For each candidate hospital, compute:

  READINESS SCORE = w1 × Facility Match Score
                  + w2 × Distance Score (inverse)
                  + w3 × Bed Availability Score
                  + w4 × Specialist Availability Score
                  + w5 × Predicted Future Availability
                  + w6 × Historical Success Rate

  Where:
    w1 = 0.30  (Does hospital HAVE what patient NEEDS?)
    w2 = 0.20  (How close is it, adjusted for traffic?)
    w3 = 0.20  (Are beds actually free right now?)
    w4 = 0.15  (Is a matching specialist on duty?)
    w5 = 0.10  (Will beds still be free when ambulance arrives?)
    w6 = 0.05  (Hospital's track record for this emergency type)

  → Rank hospitals by score
  → Select TOP hospital + BACKUP hospital

STEP 5: ROUTE OPTIMIZATION
───────────────────────────
  → Call Google Maps Directions API with:
      - Origin: Ambulance/User GPS location
      - Destination: Selected hospital
      - departure_time: now (for live traffic)
  → Get: Fastest route, ETA, distance, polyline for map
  → Also compute route to BACKUP hospital

STEP 6: PRE-ALERT NOTIFICATION
───────────────────────────────
  → Send alert to selected hospital:
      {
        patient_type: "cardiac",
        severity: "high",
        eta_minutes: 12,
        required: ["ICU", "Cardiologist"],
        ambulance_id: "AMB-042"
      }
  → Hospital dashboard shows incoming patient alert
  → Hospital can ACCEPT or REDIRECT (triggers backup)

STEP 7: LIVE TRACKING & DYNAMIC RE-ROUTING
───────────────────────────────────────────
  → Ambulance location updated every 5 seconds via WebSocket
  → If selected hospital sends "FULL" or "REDIRECT":
      → Automatically switch to BACKUP hospital
      → Recalculate route
      → Send new pre-alert
  → ETA continuously updated on all dashboards

STEP 8: ARRIVAL & HANDOFF
──────────────────────────
  → Hospital receives final notification: "Ambulance arriving in 2 min"
  → System logs response time for analytics
  → Emergency marked as COMPLETED
```

---

## 3. Data Flow Diagram Explanation

```
┌──────────┐     SOS Request        ┌──────────────┐
│  Patient  │ ────(GPS, type)──────► │  API Server   │
│  (App)    │                        │               │
└──────────┘                        │  ┌──────────┐ │
                                    │  │ Triage   │ │
                                    │  │ Module   │ │
                                    │  └────┬─────┘ │
                                    │       │       │
                                    │       ▼       │
                              ┌─────┤  ┌──────────┐ │
                              │     │  │ Hospital  │ │
     ┌──────────────┐         │     │  │ Matcher   │ │
     │  Hospital DB  │◄────────┘     │  └────┬─────┘ │
     │  (facilities, │              │       │       │
     │   beds, staff)│              │       ▼       │
     └──────────────┘              │  ┌──────────┐ │      ┌──────────────┐
                                    │  │ Scoring  │ │      │ Google Maps  │
                                    │  │ Engine   │◄├──────│ Directions   │
                                    │  └────┬─────┘ │      │ API          │
                                    │       │       │      └──────────────┘
                                    │       ▼       │
                                    │  ┌──────────┐ │      ┌──────────────┐
                                    │  │ Decision │ │      │ Hospital     │
                                    │  │ + Alert  │─├─────►│ Dashboard    │
                                    │  └────┬─────┘ │      │ (Pre-alert)  │
                                    │       │       │      └──────────────┘
                                    └───────┼───────┘
                                            │
                                            ▼
                                    ┌──────────────┐
                                    │  Route +      │
                                    │  Map to       │
                                    │  Patient App  │
                                    └──────────────┘
```

### Data Entities

| Entity              | Key Fields                                                                |
| ------------------- | ------------------------------------------------------------------------- |
| **SOS Request**     | `id, lat, lng, emergency_type, severity, timestamp, patient_notes`        |
| **Hospital**        | `id, name, lat, lng, specializations[], facilities[], total_beds`         |
| **Hospital Status** | `hospital_id, icu_available, doctors_on_duty[], equipment_status, load_%` |
| **Route**           | `origin, destination, distance_km, eta_minutes, polyline, traffic_level`  |
| **Pre-Alert**       | `hospital_id, sos_id, patient_type, eta, requirements[], status`          |
| **Ambulance**       | `id, current_lat, current_lng, status (idle/en_route), assigned_sos_id`   |

---

## 4. AI/ML Components

### 🟢 Simple Option (Recommended for Hackathon MVP)

**Rule-Based Weighted Scoring (No ML training needed)**

```python
def calculate_readiness_score(hospital, patient_needs, distance_info):
    # Facility match: what % of required facilities does hospital have?
    facility_score = len(matched_facilities) / len(required_facilities)

    # Distance score: inverse normalized (closer = higher score)
    distance_score = 1 - (distance_km / max_radius_km)

    # Bed availability: ratio of free beds
    bed_score = free_icu_beds / total_icu_beds

    # Specialist match: is a matching doctor on duty?
    specialist_score = 1.0 if matching_specialist_on_duty else 0.3

    # Predicted availability: simple linear decay model
    # "If hospital is filling up at rate X, will beds remain at ETA?"
    predicted_score = max(0, bed_score - (fill_rate * eta_hours))

    # Weighted combination
    score = (0.30 * facility_score +
             0.20 * distance_score +
             0.20 * bed_score +
             0.15 * specialist_score +
             0.10 * predicted_score +
             0.05 * historical_score)

    return score  # 0.0 to 1.0
```

**Why this works:** No training data needed. Weights are intuitive and tunable. Handles partial data gracefully (missing fields default to neutral 0.5).

### 🔵 Advanced Option (If time permits / for judges to be impressed)

| AI Component                  | Technique                       | Purpose                                 |
| ----------------------------- | ------------------------------- | --------------------------------------- |
| **Bed Availability Forecast** | Linear Regression / ARIMA       | Predict bed count at T+ETA              |
| **Demand Prediction**         | Time-series (Prophet / LSTM)    | Predict ER load by hour/day             |
| **NLP Triage**                | Text classification (BERT-tiny) | Parse patient notes into emergency type |
| **Route ETA Prediction**      | Gradient Boosted Trees          | Improve ETA beyond Google's estimate    |
| **Anomaly Detection**         | Isolation Forest                | Detect unusual hospital load patterns   |

### Handling Uncertainty (Partial / Missing Data)

```
IF hospital bed data is missing:
    → Use last known value with a confidence decay (e.g., 0.9^hours_since_update)
IF hospital has no data at all:
    → Assign neutral score (0.5) and flag as "unverified" to user
IF GPS is inaccurate:
    → Use cell tower triangulation fallback / ask user to confirm area
```

---

## 5. Recommended Tech Stack

### For Hackathon (Practical & Fast to Build)

| Layer             | Technology                   | Why                                            |
| ----------------- | ---------------------------- | ---------------------------------------------- |
| **Frontend**      | HTML + CSS + Vanilla JS      | No build tools, instant deploy, fast to code   |
| **Maps**          | Leaflet.js + OpenStreetMap   | Free, no API key needed for tiles              |
| **Routing**       | Google Maps Directions API   | Best live traffic data (free tier: 200$/mo)    |
| **Backend**       | Python Flask                 | Simple, great for prototyping, good ML support |
| **Database**      | SQLite + JSON files          | Zero setup, perfect for demos                  |
| **Real-time**     | Flask-SocketIO               | WebSocket support for live tracking            |
| **AI/ML**         | scikit-learn + NumPy         | Lightweight, no GPU needed                     |
| **Notifications** | In-app WebSocket alerts      | No external service dependency                 |
| **Deployment**    | Render / Railway / localhost | Free tier, easy deploy                         |

### For Production (Future)

| Layer             | Technology                            |
| ----------------- | ------------------------------------- |
| **Frontend**      | React Native (mobile) + Next.js (web) |
| **Backend**       | FastAPI + Celery (async tasks)        |
| **Database**      | PostgreSQL + Redis (caching)          |
| **Maps**          | Google Maps Platform (full suite)     |
| **ML Pipeline**   | TensorFlow Lite / ONNX for edge       |
| **Notifications** | Firebase Cloud Messaging + Twilio     |
| **Deployment**    | AWS ECS / Azure Container Apps        |
| **Monitoring**    | Prometheus + Grafana                  |

### Key APIs

| API                       | Use Case                 | Free Tier?   |
| ------------------------- | ------------------------ | ------------ |
| Google Maps Directions    | Route + ETA with traffic | $200/mo free |
| Google Maps Geocoding     | Address → coordinates    | $200/mo free |
| OpenStreetMap + Nominatim | Free geocoding fallback  | Fully free   |
| OpenRouteService          | Free routing alternative | 2000 req/day |

---

## 6. Unique Innovations / USP

### What makes this DIFFERENT from existing ambulance systems:

| #   | Innovation                      | Existing Systems            | Our System                                       |
| --- | ------------------------------- | --------------------------- | ------------------------------------------------ |
| 1   | **Predictive Readiness**        | Check current availability  | **Predict** availability at arrival time         |
| 2   | **Composite Scoring**           | Route to nearest hospital   | Score hospitals on 6 weighted factors            |
| 3   | **Graceful Degradation**        | Fail if data unavailable    | Work with partial data using confidence decay    |
| 4   | **Automatic Backup Routing**    | Manual re-routing           | Auto-switch to backup if primary rejects/is full |
| 5   | **Pre-Arrival Hospital Alerts** | Call hospital manually      | Automated digital pre-alert with ETA + needs     |
| 6   | **Zero-Login SOS**              | Require account/login       | One-tap, no auth required in emergencies         |
| 7   | **Specialization Matching**     | Generic hospital routing    | Match patient condition → hospital expertise     |
| 8   | **Dynamic Re-scoring**          | Static decision at dispatch | Continuously re-evaluate as conditions change    |

### 🏆 Key USP Statement (for hackathon pitch):

> _"We don't just find the nearest hospital — we find the **right** hospital that will be **ready** when you arrive."_

---

## 7. Future Scope Improvements

### Short Term (Next 3-6 months)

- [ ] **Voice-activated SOS** — "Hey Siri/Google, call ambulance" triggers SOS
- [ ] **Multi-language support** — Regional language UI for rural areas
- [ ] **Ambulance fleet management** — Assign closest available ambulance, not just route
- [ ] **Patient medical history integration** — Pull allergies, blood type from health ID
- [ ] **Offline mode** — Cache hospital data + routes for areas with poor connectivity

### Medium Term (6-12 months)

- [ ] **Computer Vision Triage** — Camera-based injury assessment (wound classification)
- [ ] **IoT Integration** — Ambulance vitals (heart rate, BP) streamed to hospital in real-time
- [ ] **Drone-first-responder** — Dispatch medical drone with AED while ambulance en route
- [ ] **Inter-hospital transfer optimization** — Smart transfers between hospitals
- [ ] **Government integration** — Connect to national 108/112 emergency systems

### Long Term (1-2 years)

- [ ] **Federated Learning** — Hospitals contribute to shared ML model without sharing patient data
- [ ] **Digital Twin of City** — Simulate emergency scenarios for resource planning
- [ ] **Autonomous ambulance routing** — Integration with self-driving emergency vehicles
- [ ] **Epidemic response mode** — Dynamically redistribute patients during disease outbreaks
- [ ] **Blockchain health records** — Tamper-proof emergency medical records

---

## Architecture Decision Records

### Why Flask over FastAPI?

- Flask has more tutorials and community support for hackathons
- Flask-SocketIO is mature and well-documented
- FastAPI's async benefits don't matter at hackathon scale

### Why SQLite over PostgreSQL?

- Zero installation, ships with Python
- Single file database, easy to demo and reset
- For 50-100 hospitals, SQLite is more than enough

### Why Leaflet over Google Maps for display?

- Completely free, no API key needed for map tiles
- Google Maps Directions API still used for routing (best traffic data)
- Leaflet is lighter and faster to set up

### Why Weighted Scoring over ML?

- No training data available for a new system
- Weights are explainable (critical for medical decisions)
- Can be tuned live during demo
- ML can be added later once historical data accumulates

---

_Document Version: 1.0 | Created for AMRITA Hackathon 2026_
