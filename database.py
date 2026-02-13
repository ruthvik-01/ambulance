"""
Database module — SQLite setup, seeding, and CRUD operations.
Supports Hospitals, Ambulances/Drivers, SOS Requests, Assignment History, and Event Log.
"""
import sqlite3
import json
import os
from config import Config


def get_db():
    os.makedirs(os.path.dirname(Config.DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS hospitals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            address TEXT,
            phone TEXT,
            specializations TEXT,
            facilities TEXT,
            total_beds INTEGER DEFAULT 0,
            icu_beds INTEGER DEFAULT 0,
            available_icu_beds INTEGER DEFAULT 0,
            available_general_beds INTEGER DEFAULT 0,
            doctors_on_duty TEXT,
            equipment_status TEXT,
            load_percentage REAL DEFAULT 0,
            historical_success_rate REAL DEFAULT 0.5,
            is_verified INTEGER DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS ambulances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_name TEXT NOT NULL,
            driver_phone TEXT,
            vehicle_number TEXT NOT NULL,
            firebase_uid TEXT,
            latitude REAL DEFAULT 0,
            longitude REAL DEFAULT 0,
            status TEXT DEFAULT 'available',
            current_sos_id INTEGER,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sos_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            emergency_type TEXT NOT NULL,
            severity TEXT DEFAULT 'medium',
            patient_notes TEXT,
            selected_hospital_id INTEGER,
            backup_hospital_id INTEGER,
            assigned_ambulance_id INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            assigned_at TIMESTAMP,
            accepted_at TIMESTAMP,
            enroute_at TIMESTAMP,
            arrived_at TIMESTAMP,
            completed_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sos_hospital_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sos_id INTEGER NOT NULL,
            hospital_id INTEGER NOT NULL,
            facility_score REAL,
            distance_score REAL,
            bed_score REAL,
            specialist_score REAL,
            prediction_score REAL,
            history_score REAL,
            total_score REAL,
            distance_km REAL,
            eta_minutes REAL
        );

        CREATE TABLE IF NOT EXISTS assignment_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sos_id INTEGER NOT NULL,
            ambulance_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            distance_km REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS event_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sos_id INTEGER,
            ambulance_id INTEGER,
            event_type TEXT NOT NULL,
            detail TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    _migrate_columns(conn)
    conn.commit()
    conn.close()


def _migrate_columns(conn):
    """Add columns that may be missing from older schema versions."""
    _add_column(conn, "ambulances", "firebase_uid", "TEXT")
    _add_column(conn, "sos_requests", "enroute_at", "TIMESTAMP")
    _add_column(conn, "sos_requests", "arrived_at", "TIMESTAMP")


def _add_column(conn, table, column, col_type):
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
    except sqlite3.OperationalError:
        pass


# ═══════════════════════════════════════════════
#  SEEDING
# ═══════════════════════════════════════════════

def seed_hospitals():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM hospitals").fetchone()[0]
    if count > 0:
        conn.close()
        return
    seed_path = os.path.join(os.path.dirname(__file__), "data", "hospitals_seed.json")
    if not os.path.exists(seed_path):
        conn.close()
        return
    with open(seed_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for h in data.get("hospitals", []):
        conn.execute("""
            INSERT INTO hospitals (
                name, latitude, longitude, address, phone,
                specializations, facilities, total_beds, icu_beds,
                available_icu_beds, available_general_beds,
                doctors_on_duty, equipment_status, load_percentage,
                historical_success_rate, is_verified
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            h["name"], h["latitude"], h["longitude"],
            h.get("address", ""), h.get("phone", ""),
            json.dumps(h.get("specializations", [])),
            json.dumps(h.get("facilities", [])),
            h.get("total_beds", 0), h.get("icu_beds", 0),
            h.get("available_icu_beds", 0), h.get("available_general_beds", 0),
            json.dumps(h.get("doctors_on_duty", [])),
            json.dumps(h.get("equipment_status", {})),
            h.get("load_percentage", 50),
            h.get("historical_success_rate", 0.5),
            1 if h.get("is_verified", False) else 0
        ))
    conn.commit()
    conn.close()
    print(f"✅ Seeded {len(data['hospitals'])} hospitals")


def seed_ambulances():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM ambulances").fetchone()[0]
    if count > 0:
        conn.close()
        return
    drivers = [
        ("Ravi Kumar", "+91-9876543210", "AP-07-AB-1234", 16.4700, 80.7400),
        ("Suresh Babu", "+91-9876543211", "AP-07-CD-5678", 16.5100, 80.6400),
        ("Venkat Rao", "+91-9876543212", "AP-07-EF-9012", 16.4500, 80.6800),
    ]
    for name, phone, vehicle, lat, lng in drivers:
        conn.execute("""
            INSERT INTO ambulances (driver_name, driver_phone, vehicle_number, latitude, longitude, status)
            VALUES (?,?,?,?,?,?)
        """, (name, phone, vehicle, lat, lng, "available"))
    conn.commit()
    conn.close()
    print(f"✅ Seeded {len(drivers)} ambulance drivers")


# ═══════════════════════════════════════════════
#  HOSPITAL HELPERS
# ═══════════════════════════════════════════════

def _parse_hospital(row):
    h = dict(row)
    for field in ("specializations", "facilities", "doctors_on_duty"):
        h[field] = json.loads(h.get(field) or "[]")
    h["equipment_status"] = json.loads(h.get("equipment_status") or "{}")
    return h

def get_all_hospitals():
    conn = get_db()
    rows = conn.execute("SELECT * FROM hospitals").fetchall()
    conn.close()
    return [_parse_hospital(r) for r in rows]

def get_hospital_by_id(hid):
    conn = get_db()
    row = conn.execute("SELECT * FROM hospitals WHERE id=?", (hid,)).fetchone()
    conn.close()
    return _parse_hospital(row) if row else None

def create_hospital(data):
    conn = get_db()
    cur = conn.execute("""
        INSERT INTO hospitals (
            name, latitude, longitude, address, phone,
            specializations, facilities, total_beds, icu_beds,
            available_icu_beds, available_general_beds,
            doctors_on_duty, load_percentage, historical_success_rate, is_verified
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        data["name"], data["latitude"], data["longitude"],
        data.get("address", ""), data.get("phone", ""),
        json.dumps(data.get("specializations", [])),
        json.dumps(data.get("facilities", [])),
        data.get("total_beds", 0), data.get("icu_beds", 0),
        data.get("available_icu_beds", 0), data.get("available_general_beds", 0),
        json.dumps(data.get("doctors_on_duty", [])),
        data.get("load_percentage", 0),
        data.get("historical_success_rate", 0.5),
        1 if data.get("is_verified") else 0
    ))
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return new_id


def update_hospital(hid, data):
    conn = get_db()
    conn.execute("""
        UPDATE hospitals SET
            name=?, latitude=?, longitude=?, address=?, phone=?,
            specializations=?, facilities=?, total_beds=?, icu_beds=?,
            available_icu_beds=?, available_general_beds=?,
            doctors_on_duty=?, load_percentage=?,
            historical_success_rate=?, is_verified=?,
            last_updated=CURRENT_TIMESTAMP
        WHERE id=?
    """, (
        data["name"], data["latitude"], data["longitude"],
        data.get("address", ""), data.get("phone", ""),
        json.dumps(data.get("specializations", [])),
        json.dumps(data.get("facilities", [])),
        data.get("total_beds", 0), data.get("icu_beds", 0),
        data.get("available_icu_beds", 0), data.get("available_general_beds", 0),
        json.dumps(data.get("doctors_on_duty", [])),
        data.get("load_percentage", 0),
        data.get("historical_success_rate", 0.5),
        1 if data.get("is_verified") else 0,
        hid
    ))
    conn.commit()
    conn.close()

def delete_hospital(hid):
    conn = get_db()
    conn.execute("DELETE FROM hospitals WHERE id=?", (hid,))
    conn.commit()
    conn.close()

def update_hospital_status(hid, updates):
    conn = get_db()
    allowed = ["available_icu_beds", "available_general_beds", "load_percentage", "doctors_on_duty", "equipment_status"]
    parts, vals = [], []
    for f in allowed:
        if f in updates:
            parts.append(f"{f}=?")
            v = updates[f]
            vals.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
    if not parts:
        conn.close()
        return False
    parts.append("last_updated=CURRENT_TIMESTAMP")
    vals.append(hid)
    conn.execute(f"UPDATE hospitals SET {', '.join(parts)} WHERE id=?", vals)
    conn.commit()
    conn.close()
    return True


# ═══════════════════════════════════════════════
#  AMBULANCE HELPERS
# ═══════════════════════════════════════════════

def get_all_ambulances():
    conn = get_db()
    rows = conn.execute("SELECT * FROM ambulances").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_ambulance_by_id(aid):
    conn = get_db()
    row = conn.execute("SELECT * FROM ambulances WHERE id=?", (aid,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_ambulance_by_firebase_uid(uid):
    conn = get_db()
    row = conn.execute("SELECT * FROM ambulances WHERE firebase_uid=?", (uid,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_available_ambulances():
    conn = get_db()
    rows = conn.execute("SELECT * FROM ambulances WHERE status='available'").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_ambulance_location(aid, lat, lng):
    conn = get_db()
    conn.execute("UPDATE ambulances SET latitude=?, longitude=?, last_updated=CURRENT_TIMESTAMP WHERE id=?", (lat, lng, aid))
    conn.commit()
    conn.close()

def update_ambulance_status(aid, status, sos_id=None):
    conn = get_db()
    conn.execute("UPDATE ambulances SET status=?, current_sos_id=?, last_updated=CURRENT_TIMESTAMP WHERE id=?", (status, sos_id, aid))
    conn.commit()
    conn.close()

def link_ambulance_firebase(aid, uid):
    conn = get_db()
    conn.execute("UPDATE ambulances SET firebase_uid=? WHERE id=?", (uid, aid))
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════
#  SOS REQUESTS
# ═══════════════════════════════════════════════

def create_sos_request(lat, lng, etype, severity="medium", notes=""):
    conn = get_db()
    cur = conn.execute("""
        INSERT INTO sos_requests (latitude, longitude, emergency_type, severity, patient_notes, status)
        VALUES (?,?,?,?,?,'pending')
    """, (lat, lng, etype, severity, notes))
    sid = cur.lastrowid
    conn.commit()
    conn.close()
    log_event(sid, None, "request_created", f"{etype}/{severity}")
    return sid

def get_sos_request(sid):
    conn = get_db()
    row = conn.execute("SELECT * FROM sos_requests WHERE id=?", (sid,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_sos_requests():
    conn = get_db()
    rows = conn.execute("SELECT * FROM sos_requests ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_active_sos_requests():
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM sos_requests
        WHERE status NOT IN ('completed','cancelled')
        ORDER BY created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_active_sos_for_driver(amb_id):
    conn = get_db()
    row = conn.execute("""
        SELECT * FROM sos_requests
        WHERE assigned_ambulance_id=? AND status IN ('assigned','accepted','enroute','arrived')
        ORDER BY created_at DESC LIMIT 1
    """, (amb_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_sos_hospitals(sid, selected_id, backup_id=None):
    conn = get_db()
    conn.execute("UPDATE sos_requests SET selected_hospital_id=?, backup_hospital_id=? WHERE id=?", (selected_id, backup_id, sid))
    conn.commit()
    conn.close()

def assign_ambulance_to_sos(sid, amb_id, distance_km=None):
    conn = get_db()
    conn.execute("UPDATE sos_requests SET assigned_ambulance_id=?, status='assigned', assigned_at=CURRENT_TIMESTAMP WHERE id=?", (amb_id, sid))
    conn.execute("UPDATE ambulances SET status='busy', current_sos_id=?, last_updated=CURRENT_TIMESTAMP WHERE id=?", (sid, amb_id))
    conn.commit()
    conn.close()
    log_event(sid, amb_id, "driver_assigned", "")
    log_assignment(sid, amb_id, "assigned", distance_km)

def accept_sos_request(sid, amb_id):
    conn = get_db()
    conn.execute("UPDATE sos_requests SET status='accepted', accepted_at=CURRENT_TIMESTAMP WHERE id=? AND assigned_ambulance_id=?", (sid, amb_id))
    conn.commit()
    conn.close()
    log_event(sid, amb_id, "driver_accepted", "")

def enroute_sos_request(sid, amb_id):
    conn = get_db()
    conn.execute("UPDATE sos_requests SET status='enroute', enroute_at=CURRENT_TIMESTAMP WHERE id=? AND assigned_ambulance_id=?", (sid, amb_id))
    conn.commit()
    conn.close()
    log_event(sid, amb_id, "status_changed", "enroute")

def arrived_sos_request(sid, amb_id):
    conn = get_db()
    conn.execute("UPDATE sos_requests SET status='arrived', arrived_at=CURRENT_TIMESTAMP WHERE id=? AND assigned_ambulance_id=?", (sid, amb_id))
    conn.commit()
    conn.close()
    log_event(sid, amb_id, "status_changed", "arrived")

def complete_sos_request(sid):
    conn = get_db()
    row = conn.execute("SELECT assigned_ambulance_id FROM sos_requests WHERE id=?", (sid,)).fetchone()
    amb_id = None
    if row and row["assigned_ambulance_id"]:
        amb_id = row["assigned_ambulance_id"]
        conn.execute("UPDATE ambulances SET status='available', current_sos_id=NULL WHERE id=?", (amb_id,))
    conn.execute("UPDATE sos_requests SET status='completed', completed_at=CURRENT_TIMESTAMP WHERE id=?", (sid,))
    conn.commit()
    conn.close()
    log_event(sid, amb_id, "trip_completed", "")

def unassign_ambulance_from_sos(sid):
    """Unassign the current driver so request can be reassigned."""
    conn = get_db()
    row = conn.execute("SELECT assigned_ambulance_id FROM sos_requests WHERE id=?", (sid,)).fetchone()
    if row and row["assigned_ambulance_id"]:
        conn.execute("UPDATE ambulances SET status='available', current_sos_id=NULL WHERE id=?", (row["assigned_ambulance_id"],))
        log_assignment(sid, row["assigned_ambulance_id"], "unassigned")
    conn.execute("UPDATE sos_requests SET assigned_ambulance_id=NULL, status='pending', assigned_at=NULL, accepted_at=NULL WHERE id=?", (sid,))
    conn.commit()
    conn.close()

def save_hospital_scores(sid, scored):
    conn = get_db()
    for sh in scored:
        conn.execute("""
            INSERT INTO sos_hospital_scores (
                sos_id, hospital_id, facility_score, distance_score,
                bed_score, specialist_score, prediction_score,
                history_score, total_score, distance_km, eta_minutes
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            sid, sh["hospital"]["id"],
            sh["scores"]["facility"], sh["scores"]["distance"],
            sh["scores"]["bed"], sh["scores"]["specialist"],
            sh["scores"]["prediction"], sh["scores"]["history"],
            sh["total_score"], sh["distance_km"], sh["eta_minutes"]
        ))
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════
#  ASSIGNMENT HISTORY & EVENT LOG
# ═══════════════════════════════════════════════

def log_assignment(sos_id, amb_id, action, distance_km=None):
    conn = get_db()
    conn.execute("INSERT INTO assignment_history (sos_id, ambulance_id, action, distance_km) VALUES (?,?,?,?)",
                 (sos_id, amb_id, action, distance_km))
    conn.commit()
    conn.close()

def log_event(sos_id, amb_id, event_type, detail=""):
    conn = get_db()
    conn.execute("INSERT INTO event_log (sos_id, ambulance_id, event_type, detail) VALUES (?,?,?,?)",
                 (sos_id, amb_id, event_type, detail))
    conn.commit()
    conn.close()

def get_events(limit=50):
    conn = get_db()
    rows = conn.execute("SELECT * FROM event_log ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_events_for_sos(sos_id):
    conn = get_db()
    rows = conn.execute("SELECT * FROM event_log WHERE sos_id=? ORDER BY created_at ASC", (sos_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
