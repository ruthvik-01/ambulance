"""
Hospital Readiness Scoring Engine — The core AI logic.

Calculates a composite readiness score for each hospital based on:
  1. Facility Match Score   (w=0.30) — Does the hospital have what the patient needs?
  2. Distance Score         (w=0.20) — How close is the hospital?
  3. Bed Availability Score (w=0.20) — Are beds free right now?
  4. Specialist Score       (w=0.15) — Is a matching specialist on duty?
  5. Predicted Availability (w=0.10) — Will beds still be free at ETA?
  6. Historical Success     (w=0.05) — Hospital's track record
"""
from math import radians, cos, sin, asin, sqrt
from config import Config

# ──────────────────────────────────────────
# Emergency type → required facilities & specialists mapping
# ──────────────────────────────────────────
EMERGENCY_REQUIREMENTS = {
    "cardiac": {
        "facilities": ["ICU", "Cath Lab", "Emergency Ward"],
        "specialists": ["Cardiologist"],
        "nice_to_have": ["MRI", "Operation Theatre", "Ventilator"],
    },
    "trauma": {
        "facilities": ["ICU", "Trauma Center", "Emergency Ward", "Operation Theatre"],
        "specialists": ["Trauma Surgeon"],
        "nice_to_have": ["Blood Bank", "CT Scan", "Ventilator"],
    },
    "maternity": {
        "facilities": ["Maternity Ward", "Operation Theatre", "NICU"],
        "specialists": ["Obstetrician"],
        "nice_to_have": ["Blood Bank", "ICU"],
    },
    "burns": {
        "facilities": ["Burns Unit", "ICU", "Emergency Ward"],
        "specialists": ["Burns Specialist"],
        "nice_to_have": ["Operation Theatre", "Blood Bank", "Ventilator"],
    },
    "neuro": {
        "facilities": ["ICU", "CT Scan", "MRI", "Emergency Ward"],
        "specialists": ["Neurologist"],
        "nice_to_have": ["Operation Theatre", "Ventilator"],
    },
    "general": {
        "facilities": ["Emergency Ward"],
        "specialists": ["General Physician"],
        "nice_to_have": ["ICU", "Blood Bank"],
    },
    "accident": {
        "facilities": ["ICU", "Trauma Center", "Emergency Ward", "Operation Theatre"],
        "specialists": ["Trauma Surgeon", "Orthopedic Surgeon"],
        "nice_to_have": ["Blood Bank", "CT Scan", "Ventilator", "Rehabilitation Center"],
    },
}


def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points
    on Earth using the Haversine formula. Returns distance in km.
    """
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371  # Earth's radius in km
    return c * r


def estimate_eta(distance_km, speed_kmh=None):
    """Estimate arrival time in minutes based on distance."""
    speed = speed_kmh or Config.AVG_AMBULANCE_SPEED_KMH
    if speed <= 0:
        speed = 40
    return (distance_km / speed) * 60  # minutes


def _calc_facility_score(hospital, requirements):
    """
    Calculate facility match score (0.0 – 1.0).
    Required facilities: weighted 80%, nice-to-have: weighted 20%.
    Handles missing data gracefully.
    """
    required = requirements.get("facilities", [])
    nice_to_have = requirements.get("nice_to_have", [])
    hospital_facilities = hospital.get("facilities", [])

    if not required:
        return 0.5  # neutral if no requirements

    # Case-insensitive matching
    hospital_set = {f.lower() for f in hospital_facilities}
    matched_required = sum(1 for f in required if f.lower() in hospital_set)
    matched_nice = sum(1 for f in nice_to_have if f.lower() in hospital_set)

    required_score = matched_required / len(required) if required else 0.5
    nice_score = matched_nice / len(nice_to_have) if nice_to_have else 0.5

    return 0.8 * required_score + 0.2 * nice_score


def _calc_distance_score(distance_km, max_radius_km=None):
    """
    Calculate distance score (0.0 – 1.0).
    Closer = higher score. Uses inverse normalization.
    """
    max_r = max_radius_km or Config.SEARCH_RADIUS_KM
    if max_r <= 0:
        max_r = 15
    score = 1.0 - min(distance_km / max_r, 1.0)
    return max(score, 0.0)


def _calc_bed_score(hospital):
    """
    Calculate bed availability score (0.0 – 1.0).
    Combines ICU and general bed availability.
    """
    icu_total = hospital.get("icu_beds", 0)
    icu_avail = hospital.get("available_icu_beds", 0)
    gen_avail = hospital.get("available_general_beds", 0)
    total_beds = hospital.get("total_beds", 1)

    if icu_total <= 0 and total_beds <= 0:
        return 0.5  # unknown → neutral

    # ICU availability is more critical (70% weight)
    icu_score = (icu_avail / icu_total) if icu_total > 0 else 0.5
    gen_score = (gen_avail / total_beds) if total_beds > 0 else 0.5

    # Also factor in overall load (lower load = better)
    load = hospital.get("load_percentage", 50) / 100.0
    load_bonus = 1.0 - load

    return 0.50 * icu_score + 0.25 * gen_score + 0.25 * load_bonus


def _calc_specialist_score(hospital, requirements):
    """
    Calculate specialist availability score (0.0 – 1.0).
    """
    needed_specialists = requirements.get("specialists", [])
    on_duty = hospital.get("doctors_on_duty", [])

    if not needed_specialists:
        return 0.5

    on_duty_lower = {d.lower() for d in on_duty}
    matched = sum(1 for s in needed_specialists if s.lower() in on_duty_lower)
    return matched / len(needed_specialists)


def _calc_prediction_score(hospital, eta_minutes):
    """
    Predict bed availability at estimated arrival time.
    Uses a simple linear decay model based on current load trend.
    """
    current_bed_score = _calc_bed_score(hospital)
    load = hospital.get("load_percentage", 50) / 100.0

    # Assume fill rate: hospitals with higher load fill faster
    # Simple model: for every 15 min, lose (load * 0.05) of bed score
    eta_hours = eta_minutes / 60.0
    fill_rate = load * 0.05
    predicted = max(0.0, current_bed_score - (fill_rate * eta_hours))

    return predicted


def _calc_history_score(hospital):
    """
    Get the historical success rate (0.0 – 1.0).
    """
    return hospital.get("historical_success_rate", 0.5)


def score_hospital(hospital, user_lat, user_lng, emergency_type):
    """
    Calculate the composite readiness score for a single hospital.

    Returns:
        dict with individual scores, total score, distance, and ETA.
    """
    requirements = EMERGENCY_REQUIREMENTS.get(
        emergency_type, EMERGENCY_REQUIREMENTS["general"]
    )

    # Distance & ETA
    distance_km = haversine(user_lat, user_lng, hospital["latitude"], hospital["longitude"])
    eta_minutes = estimate_eta(distance_km)

    # Individual scores
    facility = _calc_facility_score(hospital, requirements)
    distance = _calc_distance_score(distance_km)
    bed = _calc_bed_score(hospital)
    specialist = _calc_specialist_score(hospital, requirements)
    prediction = _calc_prediction_score(hospital, eta_minutes)
    history = _calc_history_score(hospital)

    # Weighted composite score
    total = (
        Config.WEIGHT_FACILITY * facility
        + Config.WEIGHT_DISTANCE * distance
        + Config.WEIGHT_BEDS * bed
        + Config.WEIGHT_SPECIALIST * specialist
        + Config.WEIGHT_PREDICTION * prediction
        + Config.WEIGHT_HISTORY * history
    )

    # Specialization bonus: if hospital explicitly lists this emergency type
    specializations = hospital.get("specializations", [])
    if emergency_type.lower() in [s.lower() for s in specializations]:
        total = min(total * 1.10, 1.0)  # 10% bonus, capped at 1.0

    return {
        "hospital": hospital,
        "scores": {
            "facility": round(facility, 3),
            "distance": round(distance, 3),
            "bed": round(bed, 3),
            "specialist": round(specialist, 3),
            "prediction": round(prediction, 3),
            "history": round(history, 3),
        },
        "total_score": round(total, 4),
        "distance_km": round(distance_km, 2),
        "eta_minutes": round(eta_minutes, 1),
    }


def rank_hospitals(hospitals, user_lat, user_lng, emergency_type, max_radius_km=None):
    """
    Score and rank all hospitals for a given emergency.

    Returns:
        Sorted list of scored hospitals (best first), filtered by radius.
    """
    radius = max_radius_km or Config.SEARCH_RADIUS_KM
    scored = []

    for hospital in hospitals:
        result = score_hospital(hospital, user_lat, user_lng, emergency_type)
        if result["distance_km"] <= radius:
            scored.append(result)

    # Sort by total score (descending)
    scored.sort(key=lambda x: x["total_score"], reverse=True)
    return scored


def get_best_hospitals(hospitals, user_lat, user_lng, emergency_type, max_radius_km=None):
    """
    Get the best and backup hospital recommendation.

    Returns:
        dict with "best", "backup" (if available), and "all_scored" list.
    """
    ranked = rank_hospitals(hospitals, user_lat, user_lng, emergency_type, max_radius_km)

    result = {
        "best": ranked[0] if len(ranked) > 0 else None,
        "backup": ranked[1] if len(ranked) > 1 else None,
        "all_scored": ranked,
        "total_candidates": len(ranked),
        "emergency_type": emergency_type,
        "requirements": EMERGENCY_REQUIREMENTS.get(
            emergency_type, EMERGENCY_REQUIREMENTS["general"]
        ),
    }

    return result
