"""
Database module — SQLite setup, seeding, and CRUD operations.
"""
import sqlite3
import json
import os
from config import Config


def get_db():
    """Get a database connection."""
    os.makedirs(os.path.dirname(Config.DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS hospitals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            address TEXT,
            phone TEXT,
            specializations TEXT,      -- JSON array
            facilities TEXT,           -- JSON array
            total_beds INTEGER DEFAULT 0,
            icu_beds INTEGER DEFAULT 0,
            available_icu_beds INTEGER DEFAULT 0,
            available_general_beds INTEGER DEFAULT 0,
            doctors_on_duty TEXT,      -- JSON array
            equipment_status TEXT,     -- JSON object
            load_percentage REAL DEFAULT 0,
            historical_success_rate REAL DEFAULT 0.5,
            is_verified INTEGER DEFAULT 0,
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
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (selected_hospital_id) REFERENCES hospitals(id),
            FOREIGN KEY (backup_hospital_id) REFERENCES hospitals(id)
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
            eta_minutes REAL,
            FOREIGN KEY (sos_id) REFERENCES sos_requests(id),
            FOREIGN KEY (hospital_id) REFERENCES hospitals(id)
        );
    """)

    conn.commit()
    conn.close()


def seed_hospitals():
    """Load hospital seed data from JSON if DB is empty."""
    conn = get_db()
    cursor = conn.cursor()

    count = cursor.execute("SELECT COUNT(*) FROM hospitals").fetchone()[0]
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
        cursor.execute("""
            INSERT INTO hospitals (
                name, latitude, longitude, address, phone,
                specializations, facilities, total_beds, icu_beds,
                available_icu_beds, available_general_beds,
                doctors_on_duty, equipment_status, load_percentage,
                historical_success_rate, is_verified
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    print(f"✅ Seeded {len(data['hospitals'])} hospitals into database.")


def get_all_hospitals():
    """Return all hospitals as list of dicts."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM hospitals").fetchall()
    conn.close()
    hospitals = []
    for row in rows:
        h = dict(row)
        h["specializations"] = json.loads(h["specializations"] or "[]")
        h["facilities"] = json.loads(h["facilities"] or "[]")
        h["doctors_on_duty"] = json.loads(h["doctors_on_duty"] or "[]")
        h["equipment_status"] = json.loads(h["equipment_status"] or "{}")
        hospitals.append(h)
    return hospitals


def get_hospital_by_id(hospital_id):
    """Return a single hospital by ID."""
    conn = get_db()
    row = conn.execute("SELECT * FROM hospitals WHERE id = ?", (hospital_id,)).fetchone()
    conn.close()
    if not row:
        return None
    h = dict(row)
    h["specializations"] = json.loads(h["specializations"] or "[]")
    h["facilities"] = json.loads(h["facilities"] or "[]")
    h["doctors_on_duty"] = json.loads(h["doctors_on_duty"] or "[]")
    h["equipment_status"] = json.loads(h["equipment_status"] or "{}")
    return h


def update_hospital_status(hospital_id, updates):
    """Update a hospital's real-time status."""
    conn = get_db()
    allowed_fields = [
        "available_icu_beds", "available_general_beds", "load_percentage",
        "doctors_on_duty", "equipment_status"
    ]
    set_clauses = []
    values = []
    for field in allowed_fields:
        if field in updates:
            set_clauses.append(f"{field} = ?")
            val = updates[field]
            if isinstance(val, (list, dict)):
                val = json.dumps(val)
            values.append(val)

    if not set_clauses:
        conn.close()
        return False

    set_clauses.append("last_updated = CURRENT_TIMESTAMP")
    values.append(hospital_id)

    conn.execute(
        f"UPDATE hospitals SET {', '.join(set_clauses)} WHERE id = ?",
        values
    )
    conn.commit()
    conn.close()
    return True


def create_sos_request(latitude, longitude, emergency_type, severity="medium", patient_notes=""):
    """Create a new SOS request and return its ID."""
    conn = get_db()
    cursor = conn.execute("""
        INSERT INTO sos_requests (latitude, longitude, emergency_type, severity, patient_notes)
        VALUES (?, ?, ?, ?, ?)
    """, (latitude, longitude, emergency_type, severity, patient_notes))
    sos_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return sos_id


def update_sos_hospitals(sos_id, selected_id, backup_id=None):
    """Update the selected hospital for an SOS request."""
    conn = get_db()
    conn.execute("""
        UPDATE sos_requests
        SET selected_hospital_id = ?, backup_hospital_id = ?
        WHERE id = ?
    """, (selected_id, backup_id, sos_id))
    conn.commit()
    conn.close()


def save_hospital_scores(sos_id, scored_hospitals):
    """Save the computed scores for each hospital."""
    conn = get_db()
    for sh in scored_hospitals:
        conn.execute("""
            INSERT INTO sos_hospital_scores (
                sos_id, hospital_id, facility_score, distance_score,
                bed_score, specialist_score, prediction_score,
                history_score, total_score, distance_km, eta_minutes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sos_id, sh["hospital"]["id"],
            sh["scores"]["facility"], sh["scores"]["distance"],
            sh["scores"]["bed"], sh["scores"]["specialist"],
            sh["scores"]["prediction"], sh["scores"]["history"],
            sh["total_score"], sh["distance_km"], sh["eta_minutes"]
        ))
    conn.commit()
    conn.close()


def get_sos_request(sos_id):
    """Retrieve an SOS request by ID."""
    conn = get_db()
    row = conn.execute("SELECT * FROM sos_requests WHERE id = ?", (sos_id,)).fetchone()
    conn.close()
    return dict(row) if row else None
