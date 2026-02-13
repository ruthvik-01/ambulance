# 🚑 AI-Based Smart Ambulance Routing & Hospital Facility Matching System

> _"We don't just find the nearest hospital — we find the **right** hospital that will be **ready** when you arrive."_

A smart emergency response system that intelligently selects the most suitable hospital based on patient condition, hospital facilities, bed availability, and specialist presence — then redirects to Google Maps for navigation.

---

## 🎯 Key Features

| Feature                     | Description                                   |
| --------------------------- | --------------------------------------------- |
| **One-Tap SOS**             | No login required — instant emergency trigger |
| **GPS Auto-Detection**      | Automatically captures user location          |
| **AI Readiness Scoring**    | Hospitals scored on 6 weighted factors        |
| **Specialization Matching** | Matches emergency type → hospital expertise   |
| **Google Maps Navigation**  | Direct redirect with hospital coordinates     |
| **Backup Hospital**         | Automatic fallback if primary is overloaded   |
| **Hospital Dashboard**      | Real-time bed/staff availability updates      |
| **Live WebSocket Alerts**   | Hospitals get instant emergency notifications |

---

---

## 📊 AI Readiness Score Algorithm

Each hospital is scored from 0.0 to 1.0 using a weighted composite formula:

```
READINESS SCORE = 0.30 × Facility Match
                + 0.20 × Distance (inverse)
                + 0.20 × Bed Availability
                + 0.15 × Specialist on Duty
                + 0.10 × Predicted Future Availability
                + 0.05 × Historical Success Rate

+ 10% bonus if hospital specializes in the emergency type
```

### Score Components

| Component            | Weight | What it measures                                               |
| -------------------- | ------ | -------------------------------------------------------------- |
| **Facility Match**   | 30%    | Does the hospital have ICU, Cath Lab, etc. for this emergency? |
| **Distance**         | 20%    | Closer hospitals score higher (Haversine formula)              |
| **Bed Availability** | 20%    | ICU + general bed ratio vs. total capacity                     |
| **Specialist**       | 15%    | Is a matching specialist (Cardiologist, Surgeon) on duty?      |
| **Prediction**       | 10%    | Will beds still be free when ambulance arrives? (linear decay) |
| **History**          | 5%     | Hospital's historical success rate                             |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- pip

### Setup

```bash
# 1. Navigate to project
cd ambulance

# 2. Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the application
python app.py
```

### Access the App

| Page                   | URL                             |
| ---------------------- | ------------------------------- |
| **SOS Emergency Page** | http://localhost:5000           |
| **Hospital Dashboard** | http://localhost:5000/dashboard |

---

## 📁 Project Structure

```
ambulance/
├── app.py                  # Flask server — routes + SocketIO
├── config.py               # Configuration from environment
├── database.py             # SQLite models + CRUD operations
├── scoring.py              # AI Readiness Scoring Engine
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables
├── .env.example            # Example env configuration
├── SYSTEM_DESIGN.md        # Full system design document
├── README.md               # This file
├── data/
│   ├── hospitals_seed.json # Sample hospital data (10 hospitals)
│   └── hospital.db         # SQLite database (auto-created)
├── templates/
│   ├── index.html          # SOS emergency page
│   ├── results.html        # Hospital match results
│   └── dashboard.html      # Hospital management dashboard
└── static/
    ├── css/
    │   └── style.css       # Dark theme responsive styles
    └── js/
        ├── sos.js          # SOS page logic (GPS, submit)
        ├── results.js      # Results display + navigation
        └── dashboard.js    # Dashboard + WebSocket alerts
```

---

## 🌐 API Endpoints

| Method | Endpoint                    | Description                         |
| ------ | --------------------------- | ----------------------------------- |
| `POST` | `/api/sos`                  | Submit emergency SOS request        |
| `GET`  | `/api/sos/:id`              | Get SOS request details             |
| `GET`  | `/api/hospitals`            | List all hospitals                  |
| `GET`  | `/api/hospitals/:id`        | Get hospital details                |
| `PUT`  | `/api/hospitals/:id/status` | Update hospital availability        |
| `GET`  | `/api/emergency-types`      | List emergency types & requirements |
| `GET`  | `/api/navigate/:id`         | Get Google Maps navigation URL      |

### Example: SOS Request

```bash
curl -X POST http://localhost:5000/api/sos \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 11.0168,
    "longitude": 76.9558,
    "emergency_type": "cardiac",
    "severity": "high"
  }'
```

---

## 🔑 Emergency Types

| Type        | Required Facilities                    | Specialist Needed         |
| ----------- | -------------------------------------- | ------------------------- |
| `accident`  | ICU, Trauma Center, Emergency Ward, OT | Trauma/Orthopedic Surgeon |
| `cardiac`   | ICU, Cath Lab, Emergency Ward          | Cardiologist              |
| `trauma`    | ICU, Trauma Center, Emergency Ward, OT | Trauma Surgeon            |
| `maternity` | Maternity Ward, OT, NICU               | Obstetrician              |
| `burns`     | Burns Unit, ICU, Emergency Ward        | Burns Specialist          |
| `neuro`     | ICU, CT Scan, MRI, Emergency Ward      | Neurologist               |
| `general`   | Emergency Ward                         | General Physician         |

---

## 🛡️ Graceful Degradation

The system works even with **incomplete data**:

- **Missing bed data** → Neutral score (0.5) assigned
- **No GPS** → Manual coordinate entry + demo mode
- **No Google Maps API key** → ETA estimated from distance
- **Hospital data stale** → Confidence decay applied
- **No specialist info** → Reduced weight, other factors compensate

---

## 🏆 Unique Selling Points

1. **Predictive Readiness** — Forecasts bed availability at arrival time
2. **Composite AI Scoring** — 6-factor weighted algorithm, not just distance
3. **Zero-Login SOS** — One tap, no auth in emergencies
4. **Auto Backup Routing** — Instant fallback hospital suggestion
5. **Specialization Matching** — Right hospital for the right emergency
6. **Graceful Degradation** — Works with partial/missing data

---

## 🛠️ Tech Stack

| Layer      | Technology               | Why                             |
| ---------- | ------------------------ | ------------------------------- |
| Frontend   | HTML + CSS + Vanilla JS  | No build tools, instant load    |
| Backend    | Python Flask             | Simple, fast prototyping        |
| Database   | SQLite                   | Zero setup, ships with Python   |
| Real-time  | Flask-SocketIO           | WebSocket for live alerts       |
| Navigation | Google Maps redirect     | No API key needed for redirect  |
| AI/Scoring | NumPy + custom algorithm | Lightweight, no training needed |

---

## 👥 Team

Built for **AMRITA Hackathon 2026**

---

## 📄 License

MIT License — Built for educational purposes.
