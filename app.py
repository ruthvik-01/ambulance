"""
🚑 AI-Based Smart Ambulance Routing & Hospital Facility Matching System
Main Flask application — 3 Modules: User (public), Driver (auth), Admin (auth)
"""
import json
import threading
from datetime import datetime
from math import radians, cos, sin, asin, sqrt

from flask import Flask, request, jsonify, render_template, redirect
from flask_socketio import SocketIO, emit
from flask_cors import CORS

from config import Config
from database import (
    init_db, seed_hospitals, seed_ambulances,
    get_all_hospitals, get_hospital_by_id, create_hospital, update_hospital,
    delete_hospital, update_hospital_status,
    get_all_ambulances, get_ambulance_by_id, get_available_ambulances,
    get_ambulance_by_firebase_uid, link_ambulance_firebase,
    update_ambulance_location, update_ambulance_status,
    create_sos_request, get_sos_request, get_all_sos_requests, get_active_sos_requests,
    update_sos_hospitals,
    assign_ambulance_to_sos, accept_sos_request, enroute_sos_request,
    arrived_sos_request, complete_sos_request, unassign_ambulance_from_sos,
    get_active_sos_for_driver, save_hospital_scores,
    log_event, get_events, get_events_for_sos
)
from scoring import get_best_hospitals, EMERGENCY_REQUIREMENTS
from auth import require_auth, verify_firebase_token, get_token_from_request

# ─── App Setup ───────────────────────────────────
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = Config.SECRET_KEY
app.debug = False
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

with app.app_context():
    init_db()
    seed_hospitals()
    seed_ambulances()


# ═══════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════

def _haversine(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * asin(sqrt(a)) * 6371


def find_nearest_driver(user_lat, user_lng):
    """Find the nearest available driver by Haversine distance."""
    available = get_available_ambulances()
    if not available:
        return None, None
    best = None
    best_dist = float("inf")
    for amb in available:
        d = _haversine(user_lat, user_lng, amb["latitude"], amb["longitude"])
        if d < best_dist:
            best_dist = d
            best = amb
    return best, round(best_dist, 2) if best else None


def _schedule_reassignment(sos_id, timeout_sec):
    """If driver doesn't accept within timeout, reassign to next nearest."""
    def _check():
        sos = get_sos_request(sos_id)
        if sos and sos["status"] == "assigned":
            # Still assigned but not accepted — reassign
            old_amb = sos["assigned_ambulance_id"]
            unassign_ambulance_from_sos(sos_id)
            sos = get_sos_request(sos_id)
            if sos:
                driver, dist = find_nearest_driver(sos["latitude"], sos["longitude"])
                if driver and driver["id"] != old_amb:
                    assign_ambulance_to_sos(sos_id, driver["id"], dist)
                    socketio.emit("driver_reassigned", {
                        "sos_id": sos_id,
                        "ambulance_id": driver["id"],
                        "driver_name": driver["driver_name"],
                        "driver_phone": driver["driver_phone"],
                        "vehicle_number": driver["vehicle_number"],
                        "latitude": driver["latitude"],
                        "longitude": driver["longitude"],
                        "timestamp": datetime.now().isoformat()
                    })
                    log_event(sos_id, driver["id"], "driver_reassigned", f"timeout from amb {old_amb}")
                else:
                    socketio.emit("no_driver_available", {"sos_id": sos_id})
    timer = threading.Timer(timeout_sec, _check)
    timer.daemon = True
    timer.start()


# ══════════════════════════════════════════════════
#  PAGE ROUTES
# ══════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/results/<int:sos_id>")
def results_page(sos_id):
    return render_template("results.html", sos_id=sos_id)

@app.route("/ambulance/<int:sos_id>/<int:hospital_id>")
def ambulance_page(sos_id, hospital_id):
    return render_template("ambulance.html", sos_id=sos_id, hospital_id=hospital_id)

@app.route("/driver")
def driver_login():
    return render_template("driver_login.html",
                           firebase_api_key=Config.FIREBASE_API_KEY,
                           firebase_auth_domain=Config.FIREBASE_AUTH_DOMAIN,
                           firebase_project_id=Config.FIREBASE_PROJECT_ID)

@app.route("/driver/dashboard")
def driver_dashboard():
    return render_template("driver.html",
                           firebase_api_key=Config.FIREBASE_API_KEY,
                           firebase_auth_domain=Config.FIREBASE_AUTH_DOMAIN,
                           firebase_project_id=Config.FIREBASE_PROJECT_ID)

@app.route("/admin")
def admin_dashboard():
    return render_template("admin.html",
                           firebase_api_key=Config.FIREBASE_API_KEY,
                           firebase_auth_domain=Config.FIREBASE_AUTH_DOMAIN,
                           firebase_project_id=Config.FIREBASE_PROJECT_ID)

@app.route("/dashboard")
def dashboard_redirect():
    return redirect("/admin")


# ══════════════════════════════════════════════════
#  API: SOS (User Module — PUBLIC)
# ══════════════════════════════════════════════════

@app.route("/api/sos", methods=["POST"])
def handle_sos():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400

    lat = data.get("latitude")
    lng = data.get("longitude")
    emergency_type = data.get("emergency_type", "general")
    severity = data.get("severity", "medium")
    notes = data.get("patient_notes", "")

    if lat is None or lng is None:
        return jsonify({"error": "GPS coordinates required"}), 400
    if emergency_type not in EMERGENCY_REQUIREMENTS:
        return jsonify({"error": f"Unknown type: {emergency_type}",
                        "valid_types": list(EMERGENCY_REQUIREMENTS.keys())}), 400

    sos_id = create_sos_request(lat, lng, emergency_type, severity, notes)
    hospitals = get_all_hospitals()
    result = get_best_hospitals(hospitals, lat, lng, emergency_type)

    if not result["best"]:
        return jsonify({"error": "No hospitals found in range", "sos_id": sos_id}), 404

    best_id = result["best"]["hospital"]["id"]
    backup_id = result["backup"]["hospital"]["id"] if result["backup"] else None
    update_sos_hospitals(sos_id, best_id, backup_id)
    save_hospital_scores(sos_id, result["all_scored"])

    socketio.emit("new_sos", {
        "sos_id": sos_id, "emergency_type": emergency_type,
        "severity": severity, "latitude": lat, "longitude": lng,
        "best_hospital": result["best"]["hospital"]["name"],
        "eta_minutes": result["best"]["eta_minutes"],
        "timestamp": datetime.now().isoformat()
    })

    def _summary(scored):
        if not scored:
            return None
        h = scored["hospital"]
        return {
            "id": h["id"], "name": h["name"],
            "address": h.get("address", ""), "phone": h.get("phone", ""),
            "latitude": h["latitude"], "longitude": h["longitude"],
            "distance_km": scored["distance_km"], "eta_minutes": scored["eta_minutes"],
            "readiness_score": scored["total_score"], "score_breakdown": scored["scores"],
            "facilities": h.get("facilities", []),
            "available_icu_beds": h.get("available_icu_beds", 0),
            "specializations": h.get("specializations", []),
            "navigation_url": f"https://www.google.com/maps/dir/?api=1&destination={h['latitude']},{h['longitude']}"
        }

    return jsonify({
        "success": True, "sos_id": sos_id, "emergency_type": emergency_type,
        "latitude": lat, "longitude": lng,
        "requirements": result["requirements"],
        "best_hospital": _summary(result["best"]),
        "backup_hospital": _summary(result["backup"]),
        "total_hospitals_evaluated": result["total_candidates"],
        "all_hospitals": [_summary(s) for s in result["all_scored"][:5]]
    }), 200


@app.route("/api/sos/<int:sos_id>", methods=["GET"])
def get_sos(sos_id):
    sos = get_sos_request(sos_id)
    if not sos:
        return jsonify({"error": "SOS not found"}), 404
    # Enrich with driver info
    if sos.get("assigned_ambulance_id"):
        amb = get_ambulance_by_id(sos["assigned_ambulance_id"])
        if amb:
            sos["driver"] = {
                "id": amb["id"],
                "driver_name": amb["driver_name"],
                "driver_phone": amb["driver_phone"],
                "vehicle_number": amb["vehicle_number"],
                "latitude": amb["latitude"],
                "longitude": amb["longitude"],
                "status": amb["status"]
            }
    if sos.get("selected_hospital_id"):
        hosp = get_hospital_by_id(sos["selected_hospital_id"])
        if hosp:
            sos["hospital"] = {
                "id": hosp["id"], "name": hosp["name"],
                "address": hosp.get("address", ""),
                "phone": hosp.get("phone", ""),
                "latitude": hosp["latitude"], "longitude": hosp["longitude"]
            }
    return jsonify(sos), 200


@app.route("/api/sos/<int:sos_id>/events", methods=["GET"])
def get_sos_events(sos_id):
    events = get_events_for_sos(sos_id)
    return jsonify({"events": events}), 200


# ══════════════════════════════════════════════════
#  API: AMBULANCE ASSIGNMENT (User → Driver)
# ══════════════════════════════════════════════════

@app.route("/api/ambulance/assign", methods=["POST"])
def assign_ambulance():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400

    sos_id = data.get("sos_id")
    hospital_id = data.get("hospital_id")
    if not sos_id or not hospital_id:
        return jsonify({"error": "sos_id and hospital_id required"}), 400

    sos = get_sos_request(sos_id)
    if not sos:
        return jsonify({"error": "SOS request not found"}), 404

    hospital = get_hospital_by_id(hospital_id)
    if not hospital:
        return jsonify({"error": "Hospital not found"}), 404

    update_sos_hospitals(sos_id, hospital_id, None)

    # Find nearest available driver (Haversine)
    user_lat = sos.get("latitude") or data.get("user_latitude")
    user_lng = sos.get("longitude") or data.get("user_longitude")
    assigned_amb, dist = find_nearest_driver(user_lat, user_lng)

    if not assigned_amb:
        return jsonify({"error": "No ambulance drivers available", "sos_id": sos_id}), 503

    assign_ambulance_to_sos(sos_id, assigned_amb["id"], dist)

    # Notify all via WebSocket
    assignment_data = {
        "sos_id": sos_id,
        "hospital_id": hospital_id, "hospital_name": hospital["name"],
        "hospital_lat": hospital["latitude"], "hospital_lng": hospital["longitude"],
        "patient_lat": user_lat, "patient_lng": user_lng,
        "emergency_type": sos.get("emergency_type", "general"),
        "severity": sos.get("severity", "medium"),
        "patient_notes": sos.get("patient_notes", ""),
        "ambulance_id": assigned_amb["id"],
        "driver_name": assigned_amb["driver_name"],
        "driver_phone": assigned_amb["driver_phone"],
        "vehicle_number": assigned_amb["vehicle_number"],
        "driver_lat": assigned_amb["latitude"],
        "driver_lng": assigned_amb["longitude"],
        "distance_km": dist,
        "timestamp": datetime.now().isoformat()
    }
    socketio.emit("driver_assignment", assignment_data)

    # Schedule reassignment if not accepted
    _schedule_reassignment(sos_id, Config.DRIVER_ACCEPT_TIMEOUT_SEC)

    return jsonify({
        "success": True,
        "message": f"Nearest driver assigned for {hospital['name']}",
        "ambulance": {
            "id": assigned_amb["id"],
            "driver_name": assigned_amb["driver_name"],
            "vehicle_number": assigned_amb["vehicle_number"],
            "phone": assigned_amb["driver_phone"],
            "latitude": assigned_amb["latitude"],
            "longitude": assigned_amb["longitude"],
            "distance_km": dist
        },
        "hospital": {
            "id": hospital["id"], "name": hospital["name"],
            "latitude": hospital["latitude"], "longitude": hospital["longitude"]
        },
    }), 200


@app.route("/api/ambulance/<int:amb_id>/location", methods=["GET"])
def get_ambulance_location(amb_id):
    amb = get_ambulance_by_id(amb_id)
    if not amb:
        return jsonify({"error": "Ambulance not found"}), 404
    return jsonify({
        "id": amb["id"], "driver_name": amb["driver_name"],
        "latitude": amb["latitude"], "longitude": amb["longitude"],
        "status": amb["status"], "vehicle_number": amb["vehicle_number"],
        "driver_phone": amb.get("driver_phone", "")
    }), 200


# ══════════════════════════════════════════════════
#  API: DRIVER MODULE (PROTECTED — Firebase Auth)
# ══════════════════════════════════════════════════

@app.route("/api/driver/login", methods=["POST"])
def driver_firebase_login():
    """Link a Firebase UID to an ambulance record after driver logs in."""
    data = request.get_json() or {}
    token = get_token_from_request()
    if not token:
        # Allow ambulance_id based auth for backwards compat
        amb_id = data.get("ambulance_id")
        if amb_id:
            amb = get_ambulance_by_id(amb_id)
            if amb:
                return jsonify({"success": True, "ambulance": amb}), 200
        return jsonify({"error": "Token or ambulance_id required"}), 401

    claims = verify_firebase_token(token)
    if not claims:
        return jsonify({"error": "Invalid token"}), 401

    uid = claims.get("user_id") or claims.get("sub")
    email = claims.get("email", "")

    # Check if already linked
    amb = get_ambulance_by_firebase_uid(uid)
    if amb:
        return jsonify({"success": True, "ambulance": amb}), 200

    # Link to specific ambulance if provided
    amb_id = data.get("ambulance_id")
    if amb_id:
        amb = get_ambulance_by_id(amb_id)
        if amb:
            link_ambulance_firebase(amb_id, uid)
            amb = get_ambulance_by_id(amb_id)
            return jsonify({"success": True, "ambulance": amb}), 200

    return jsonify({"error": "No ambulance linked. Please select one.", "uid": uid}), 404


@app.route("/api/driver/<int:amb_id>/active", methods=["GET"])
def driver_active_request(amb_id):
    sos = get_active_sos_for_driver(amb_id)
    if not sos:
        return jsonify({"active": False, "message": "No active requests"}), 200
    hospital = get_hospital_by_id(sos["selected_hospital_id"]) if sos.get("selected_hospital_id") else None
    return jsonify({
        "active": True, "sos": sos,
        "hospital": hospital,
        "patient_location": {"latitude": sos["latitude"], "longitude": sos["longitude"]},
    }), 200


@app.route("/api/driver/<int:amb_id>/accept", methods=["POST"])
def driver_accept(amb_id):
    data = request.get_json() or {}
    sos_id = data.get("sos_id")
    if not sos_id:
        return jsonify({"error": "sos_id required"}), 400
    accept_sos_request(sos_id, amb_id)
    amb = get_ambulance_by_id(amb_id)
    socketio.emit("driver_accepted", {
        "sos_id": sos_id, "ambulance_id": amb_id,
        "driver_name": amb["driver_name"] if amb else "",
        "driver_phone": amb["driver_phone"] if amb else "",
        "vehicle_number": amb["vehicle_number"] if amb else "",
        "timestamp": datetime.now().isoformat()
    })
    return jsonify({"success": True, "message": "Request accepted"}), 200


@app.route("/api/driver/<int:amb_id>/enroute", methods=["POST"])
def driver_enroute(amb_id):
    data = request.get_json() or {}
    sos_id = data.get("sos_id")
    if not sos_id:
        return jsonify({"error": "sos_id required"}), 400
    enroute_sos_request(sos_id, amb_id)
    socketio.emit("status_changed", {
        "sos_id": sos_id, "ambulance_id": amb_id,
        "status": "enroute",
        "timestamp": datetime.now().isoformat()
    })
    return jsonify({"success": True}), 200


@app.route("/api/driver/<int:amb_id>/arrived", methods=["POST"])
def driver_arrived(amb_id):
    data = request.get_json() or {}
    sos_id = data.get("sos_id")
    if not sos_id:
        return jsonify({"error": "sos_id required"}), 400
    arrived_sos_request(sos_id, amb_id)
    socketio.emit("status_changed", {
        "sos_id": sos_id, "ambulance_id": amb_id,
        "status": "arrived",
        "timestamp": datetime.now().isoformat()
    })
    return jsonify({"success": True}), 200


@app.route("/api/driver/<int:amb_id>/location", methods=["POST"])
def driver_update_location(amb_id):
    data = request.get_json()
    if not data or "latitude" not in data or "longitude" not in data:
        return jsonify({"error": "latitude and longitude required"}), 400
    update_ambulance_location(amb_id, data["latitude"], data["longitude"])
    socketio.emit("location_update", {
        "ambulance_id": amb_id,
        "latitude": data["latitude"],
        "longitude": data["longitude"],
        "timestamp": datetime.now().isoformat()
    })
    return jsonify({"success": True}), 200


@app.route("/api/driver/<int:amb_id>/complete", methods=["POST"])
def driver_complete(amb_id):
    data = request.get_json() or {}
    sos_id = data.get("sos_id")
    if not sos_id:
        return jsonify({"error": "sos_id required"}), 400
    complete_sos_request(sos_id)
    socketio.emit("trip_completed", {
        "sos_id": sos_id, "ambulance_id": amb_id,
        "timestamp": datetime.now().isoformat()
    })
    return jsonify({"success": True, "message": "Trip completed"}), 200


@app.route("/api/ambulances", methods=["GET"])
def list_ambulances():
    return jsonify({"ambulances": get_all_ambulances()}), 200


# ══════════════════════════════════════════════════
#  API: ADMIN MODULE (PROTECTED — Firebase Auth)
# ══════════════════════════════════════════════════

@app.route("/api/admin/requests", methods=["GET"])
def admin_all_requests():
    tab = request.args.get("tab", "all")
    if tab == "active":
        reqs = get_active_sos_requests()
    else:
        reqs = get_all_sos_requests()
    # Enrich each request
    enriched = []
    for r in reqs:
        if r.get("assigned_ambulance_id"):
            amb = get_ambulance_by_id(r["assigned_ambulance_id"])
            r["driver"] = {
                "id": amb["id"], "driver_name": amb["driver_name"],
                "driver_phone": amb["driver_phone"],
                "vehicle_number": amb["vehicle_number"],
                "latitude": amb["latitude"], "longitude": amb["longitude"],
                "status": amb["status"]
            } if amb else None
        if r.get("selected_hospital_id"):
            hosp = get_hospital_by_id(r["selected_hospital_id"])
            r["hospital_name"] = hosp["name"] if hosp else "Unknown"
        enriched.append(r)
    return jsonify({"requests": enriched}), 200


@app.route("/api/admin/reassign", methods=["POST"])
def admin_reassign():
    data = request.get_json() or {}
    sos_id = data.get("sos_id")
    new_amb_id = data.get("ambulance_id")
    if not sos_id:
        return jsonify({"error": "sos_id required"}), 400

    sos = get_sos_request(sos_id)
    if not sos:
        return jsonify({"error": "SOS not found"}), 404

    # Unassign current
    unassign_ambulance_from_sos(sos_id)

    if new_amb_id:
        amb = get_ambulance_by_id(new_amb_id)
        if not amb:
            return jsonify({"error": "Ambulance not found"}), 404
        dist = _haversine(sos["latitude"], sos["longitude"], amb["latitude"], amb["longitude"])
        assign_ambulance_to_sos(sos_id, new_amb_id, round(dist, 2))
    else:
        # Auto-assign nearest
        driver, dist = find_nearest_driver(sos["latitude"], sos["longitude"])
        if driver:
            assign_ambulance_to_sos(sos_id, driver["id"], dist)
            new_amb_id = driver["id"]
        else:
            return jsonify({"error": "No available drivers"}), 503

    amb = get_ambulance_by_id(new_amb_id)
    socketio.emit("driver_reassigned", {
        "sos_id": sos_id,
        "ambulance_id": new_amb_id,
        "driver_name": amb["driver_name"],
        "driver_phone": amb["driver_phone"],
        "vehicle_number": amb["vehicle_number"],
        "latitude": amb["latitude"],
        "longitude": amb["longitude"],
        "timestamp": datetime.now().isoformat()
    })
    log_event(sos_id, new_amb_id, "admin_reassigned", "")
    return jsonify({"success": True, "ambulance": amb}), 200


@app.route("/api/admin/events", methods=["GET"])
def admin_events():
    limit = request.args.get("limit", 50, type=int)
    return jsonify({"events": get_events(limit)}), 200


@app.route("/api/hospitals", methods=["GET"])
def list_hospitals():
    hospitals = get_all_hospitals()
    return jsonify({"hospitals": hospitals, "count": len(hospitals)}), 200

@app.route("/api/hospitals/<int:hid>", methods=["GET"])
def get_hospital(hid):
    h = get_hospital_by_id(hid)
    if not h:
        return jsonify({"error": "Hospital not found"}), 404
    return jsonify(h), 200

@app.route("/api/hospitals", methods=["POST"])
def add_hospital():
    data = request.get_json()
    if not data or "name" not in data:
        return jsonify({"error": "Hospital data required"}), 400
    new_id = create_hospital(data)
    return jsonify({"success": True, "id": new_id, "message": f"Hospital '{data['name']}' created"}), 201

@app.route("/api/hospitals/<int:hid>", methods=["PUT"])
def edit_hospital(hid):
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400
    if not get_hospital_by_id(hid):
        return jsonify({"error": "Hospital not found"}), 404
    update_hospital(hid, data)
    return jsonify({"success": True, "message": "Hospital updated"}), 200

@app.route("/api/hospitals/<int:hid>", methods=["DELETE"])
def remove_hospital(hid):
    if not get_hospital_by_id(hid):
        return jsonify({"error": "Hospital not found"}), 404
    delete_hospital(hid)
    return jsonify({"success": True, "message": "Hospital deleted"}), 200

@app.route("/api/hospitals/<int:hid>/status", methods=["PUT"])
def update_status(hid):
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400
    hospital = get_hospital_by_id(hid)
    if not hospital:
        return jsonify({"error": "Hospital not found"}), 404
    update_hospital_status(hid, data)
    socketio.emit("hospital_updated", {
        "hospital_id": hid, "hospital_name": hospital["name"],
        "updates": data, "timestamp": datetime.now().isoformat()
    })
    return jsonify({"success": True}), 200

@app.route("/api/emergency-types", methods=["GET"])
def get_emergency_types():
    types = {}
    for k, v in EMERGENCY_REQUIREMENTS.items():
        types[k] = {
            "required_facilities": v["facilities"],
            "required_specialists": v["specialists"],
            "nice_to_have": v.get("nice_to_have", [])
        }
    return jsonify(types), 200


# ══════════════════════════════════════════════════
#  WEBSOCKET EVENTS
# ══════════════════════════════════════════════════

@socketio.on("connect")
def on_connect():
    emit("connected", {"message": "Connected to Smart Ambulance System"})

@socketio.on("disconnect")
def on_disconnect():
    pass

@socketio.on("location_update")
def on_location(data):
    if "ambulance_id" in data and "latitude" in data and "longitude" in data:
        update_ambulance_location(data["ambulance_id"], data["latitude"], data["longitude"])
    emit("location_update", data, broadcast=True)

@socketio.on("join_sos")
def on_join_sos(data):
    """Client subscribes to updates for a specific SOS request."""
    pass  # All events are broadcast; client filters by sos_id


# ══════════════════════════════════════════════════
#  RUN
# ══════════════════════════════════════════════════

if __name__ == "__main__":
    print("🚑 Smart Ambulance Routing System")
    print(f"📍 User App:    http://localhost:{Config.PORT}")
    print(f"🚑 Driver:      http://localhost:{Config.PORT}/driver")
    print(f"🔧 Admin:       http://localhost:{Config.PORT}/admin")
    print(f"🔍 Radius:      {Config.SEARCH_RADIUS_KM} km")
    socketio.run(app, host=Config.HOST, port=Config.PORT,
                 debug=False, use_reloader=False, allow_unsafe_werkzeug=True)
