# 🚑 Smart Ambulance — Runbook

## Quick Start

```powershell
cd ambulance
pip install -r requirements.txt
python app.py
```

Open:

- **User SOS**: http://localhost:5000
- **Driver Portal**: http://localhost:5000/driver
- **Admin Dashboard**: http://localhost:5000/admin

## Environment Variables (Optional)

Create a `.env` file in the project root:

```env
SECRET_KEY=your-secret-key
PORT=5000
HOST=0.0.0.0
SEARCH_RADIUS_KM=50

# Firebase (optional — app works without it in demo mode)
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_API_KEY=your-api-key
FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
```

## Firebase Setup (Optional)

1. Go to [Firebase Console](https://console.firebase.google.com) → Create Project
2. Enable **Authentication** → Email/Password sign-in
3. Create driver/admin accounts in Firebase Auth
4. Copy config values from **Project Settings** → **General** → Web App
5. Set `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `FIREBASE_PROJECT_ID` in `.env`

> Without Firebase, the app runs in **demo mode** — driver & admin login is bypassed.

## Architecture

```
User (public)  →  POST /api/sos  →  Hospital Scoring Engine  →  Results Page
                                                              →  Dispatch Ambulance
                                                              →  Nearest Driver (Haversine)
Driver (auth)  →  Socket.IO notifications  →  Accept/Enroute/Arrived/Complete
Admin (auth)   →  Live dashboard  →  Reassign  →  Event Feed
```

### Status Flow

```
pending → assigned → accepted → enroute → arrived → completed
```

### Key Features

- **AI Hospital Scoring**: 6-factor weighted scoring (facility match, distance, bed availability, specialist, prediction, history)
- **Nearest Driver**: Haversine distance calculation for auto-assignment
- **Reassignment Timeout**: If driver doesn't accept within 60s, auto-reassign to next nearest
- **Real-time**: Socket.IO events for all state changes
- **Audit Trail**: `event_log` and `assignment_history` tables

## API Reference

| Method | Endpoint                       | Auth     | Description                       |
| ------ | ------------------------------ | -------- | --------------------------------- |
| POST   | `/api/sos`                     | Public   | Create SOS request                |
| GET    | `/api/sos/<id>`                | Public   | Get SOS with driver/hospital info |
| POST   | `/api/ambulance/assign`        | Public   | Assign nearest driver             |
| GET    | `/api/ambulance/<id>/location` | Public   | Get driver location               |
| POST   | `/api/driver/login`            | Token/ID | Link Firebase UID to ambulance    |
| GET    | `/api/driver/<id>/active`      | —        | Get active request for driver     |
| POST   | `/api/driver/<id>/accept`      | —        | Accept SOS request                |
| POST   | `/api/driver/<id>/enroute`     | —        | Mark en route                     |
| POST   | `/api/driver/<id>/arrived`     | —        | Mark arrived                      |
| POST   | `/api/driver/<id>/complete`    | —        | Complete trip                     |
| POST   | `/api/driver/<id>/location`    | —        | Update driver GPS                 |
| GET    | `/api/admin/requests`          | —        | List all SOS requests             |
| POST   | `/api/admin/reassign`          | —        | Manual reassignment               |
| GET    | `/api/admin/events`            | —        | Event feed                        |
| GET    | `/api/hospitals`               | Public   | List hospitals                    |
| GET    | `/api/emergency-types`         | Public   | List emergency types              |

## Test Checklist

- [ ] Open http://localhost:5000 — GPS prompt appears
- [ ] Select emergency type → tap SOS → redirects to results
- [ ] Results page shows best + backup hospital with scores
- [ ] Click "Dispatch Ambulance" → redirects to tracking page
- [ ] Tracking page shows timeline: Requested → Assigned
- [ ] Open /driver in another tab → Quick Login with an ambulance
- [ ] Driver dashboard shows incoming request
- [ ] Accept → En Route → Arrived → Complete flow works
- [ ] Admin dashboard shows live request cards and event feed
- [ ] Admin reassignment works
- [ ] Socket.IO events update all pages in real-time
