"""
🚑 AI-Based Smart Ambulance Routing & Hospital Facility Matching System
Main Flask application with REST API and SocketIO support.
"""
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_socketio import SocketIO, emit
from flask_cors import CORS

from config import Config
from database import (
    init_db, seed_hospitals, get_all_hospitals, get_hospital_by_id,
    update_hospital_status, create_sos_request, update_sos_hospitals,
    save_hospital_scores, get_sos_request
)
from scoring import get_best_hospitals, EMERGENCY_REQUIREMENTS

# ─── App Setup ────────────────────────────────────────
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = Config.SECRET_KEY
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# ─── Initialize DB on startup ─────────────────────────
with app.app_context():
    init_db()
    seed_hospitals()

# ══════════════════════════════════════════════════════
#  PAGE ROUTES
# ══════════════════════════════════════════════════════

@app.route("/")
def index():
    """Main SOS page."""
    return render_template("index.html")


@app.route("/results/<int:sos_id>")
def results_page(sos_id):
    """Results page showing matched hospitals."""
    return render_template("results.html", sos_id=sos_id)


@app.route("/dashboard")
def dashboard():
    """Hospital dashboard to manage availability."""
    return render_template("dashboard.html")


# ══════════════════════════════════════════════════════
#  API ROUTES
# ══════════════════════════════════════════════════════

@app.route("/api/sos", methods=["POST"])
def handle_sos():
    """
    Handle an SOS emergency request.

    Expects JSON:
    {
        "latitude": 11.0168,
        "longitude": 76.9558,
        "emergency_type": "cardiac",
        "severity": "high",        // optional
        "patient_notes": "..."     // optional
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "No JSON data provided"}), 400

    lat = data.get("latitude")
    lng = data.get("longitude")
    emergency_type = data.get("emergency_type", "general")
    severity = data.get("severity", "medium")
    notes = data.get("patient_notes", "")

    if lat is None or lng is None:
        return jsonify({"error": "GPS coordinates (latitude, longitude) required"}), 400

    if emergency_type not in EMERGENCY_REQUIREMENTS:
        return jsonify({
            "error": f"Unknown emergency type: {emergency_type}",
            "valid_types": list(EMERGENCY_REQUIREMENTS.keys())
        }), 400

    # 1. Create SOS record
    sos_id = create_sos_request(lat, lng, emergency_type, severity, notes)

    # 2. Get all hospitals and score them
    hospitals = get_all_hospitals()
    result = get_best_hospitals(hospitals, lat, lng, emergency_type)

    if not result["best"]:
        return jsonify({
            "error": "No hospitals found within search radius",
            "sos_id": sos_id,
            "search_radius_km": Config.SEARCH_RADIUS_KM
        }), 404

    # 3. Save selected hospitals
    best_id = result["best"]["hospital"]["id"]
    backup_id = result["backup"]["hospital"]["id"] if result["backup"] else None
    update_sos_hospitals(sos_id, best_id, backup_id)

    # 4. Save all scores for analytics
    save_hospital_scores(sos_id, result["all_scored"])

    # 5. Emit real-time alert to hospital dashboard
    socketio.emit("new_sos", {
        "sos_id": sos_id,
        "emergency_type": emergency_type,
        "severity": severity,
        "best_hospital": result["best"]["hospital"]["name"],
        "eta_minutes": result["best"]["eta_minutes"],
        "timestamp": datetime.now().isoformat()
    })

    # 6. Build response
    def _hospital_summary(scored):
        if not scored:
            return None
        h = scored["hospital"]
        return {
            "id": h["id"],
            "name": h["name"],
            "address": h.get("address", ""),
            "phone": h.get("phone", ""),
            "latitude": h["latitude"],
            "longitude": h["longitude"],
            "distance_km": scored["distance_km"],
            "eta_minutes": scored["eta_minutes"],
            "readiness_score": scored["total_score"],
            "score_breakdown": scored["scores"],
            "facilities": h.get("facilities", []),
            "available_icu_beds": h.get("available_icu_beds", 0),
            "specializations": h.get("specializations", []),
            "navigation_url": f"https://www.google.com/maps/dir/?api=1&destination={h['latitude']},{h['longitude']}"
        }

    response = {
        "success": True,
        "sos_id": sos_id,
        "emergency_type": emergency_type,
        "requirements": result["requirements"],
        "best_hospital": _hospital_summary(result["best"]),
        "backup_hospital": _hospital_summary(result["backup"]),
        "total_hospitals_evaluated": result["total_candidates"],
        "all_hospitals": [_hospital_summary(s) for s in result["all_scored"][:5]]
    }

    return jsonify(response), 200


@app.route("/api/sos/<int:sos_id>", methods=["GET"])
def get_sos(sos_id):
    """Get details of an SOS request."""
    sos = get_sos_request(sos_id)
    if not sos:
        return jsonify({"error": "SOS request not found"}), 404
    return jsonify(sos), 200


@app.route("/api/hospitals", methods=["GET"])
def list_hospitals():
    """List all hospitals with optional type filter."""
    hospitals = get_all_hospitals()
    emergency_type = request.args.get("type")

    if emergency_type:
        hospitals = [
            h for h in hospitals
            if emergency_type.lower() in [s.lower() for s in h.get("specializations", [])]
        ]

    return jsonify({
        "hospitals": hospitals,
        "count": len(hospitals)
    }), 200


@app.route("/api/hospitals/<int:hospital_id>", methods=["GET"])
def get_hospital(hospital_id):
    """Get a single hospital's details."""
    hospital = get_hospital_by_id(hospital_id)
    if not hospital:
        return jsonify({"error": "Hospital not found"}), 404
    return jsonify(hospital), 200


@app.route("/api/hospitals/<int:hospital_id>/status", methods=["PUT"])
def update_status(hospital_id):
    """
    Update a hospital's real-time availability.

    Expects JSON with any of:
    {
        "available_icu_beds": 5,
        "available_general_beds": 20,
        "load_percentage": 72,
        "doctors_on_duty": ["Cardiologist", "Surgeon"]
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    hospital = get_hospital_by_id(hospital_id)
    if not hospital:
        return jsonify({"error": "Hospital not found"}), 404

    success = update_hospital_status(hospital_id, data)
    if success:
        # Notify all connected clients of the status change
        socketio.emit("hospital_updated", {
            "hospital_id": hospital_id,
            "hospital_name": hospital["name"],
            "updates": data,
            "timestamp": datetime.now().isoformat()
        })
        return jsonify({"success": True, "message": "Status updated"}), 200
    return jsonify({"error": "No valid fields to update"}), 400


@app.route("/api/emergency-types", methods=["GET"])
def get_emergency_types():
    """Return available emergency types and their requirements."""
    types = {}
    for key, val in EMERGENCY_REQUIREMENTS.items():
        types[key] = {
            "required_facilities": val["facilities"],
            "required_specialists": val["specialists"],
            "nice_to_have_facilities": val.get("nice_to_have", [])
        }
    return jsonify(types), 200


@app.route("/api/navigate/<int:hospital_id>", methods=["GET"])
def navigate(hospital_id):
    """Generate Google Maps navigation URL for a hospital."""
    hospital = get_hospital_by_id(hospital_id)
    if not hospital:
        return jsonify({"error": "Hospital not found"}), 404

    nav_url = f"https://www.google.com/maps/dir/?api=1&destination={hospital['latitude']},{hospital['longitude']}"

    return jsonify({
        "hospital_name": hospital["name"],
        "latitude": hospital["latitude"],
        "longitude": hospital["longitude"],
        "navigation_url": nav_url
    }), 200


# ══════════════════════════════════════════════════════
#  WEBSOCKET EVENTS
# ══════════════════════════════════════════════════════

@socketio.on("connect")
def handle_connect():
    print(f"🔌 Client connected: {request.sid}")
    emit("connected", {"message": "Connected to ambulance routing system"})


@socketio.on("disconnect")
def handle_disconnect():
    print(f"🔌 Client disconnected: {request.sid}")


@socketio.on("location_update")
def handle_location_update(data):
    """Handle real-time location updates from ambulance."""
    emit("ambulance_location", data, broadcast=True)


# ══════════════════════════════════════════════════════
#  RUN
# ══════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🚑 Starting Smart Ambulance Routing System...")
    print(f"📍 Server: http://localhost:{Config.PORT}")
    print(f"📊 Dashboard: http://localhost:{Config.PORT}/dashboard")
    print(f"🔍 Search radius: {Config.SEARCH_RADIUS_KM} km")
    socketio.run(app, host=Config.HOST, port=Config.PORT, debug=False, allow_unsafe_werkzeug=True)
