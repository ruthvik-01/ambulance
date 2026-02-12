"""
Application configuration loaded from environment variables.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Server
    HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    PORT = int(os.getenv("FLASK_PORT", 5000))
    DEBUG = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    SECRET_KEY = os.getenv("SECRET_KEY", "ambulance-sos-secret-key-2026")

    # Google Maps (optional)
    GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

    # Search
    SEARCH_RADIUS_KM = float(os.getenv("SEARCH_RADIUS_KM", 15))

    # Scoring weights
    WEIGHT_FACILITY = float(os.getenv("WEIGHT_FACILITY", 0.30))
    WEIGHT_DISTANCE = float(os.getenv("WEIGHT_DISTANCE", 0.20))
    WEIGHT_BEDS = float(os.getenv("WEIGHT_BEDS", 0.20))
    WEIGHT_SPECIALIST = float(os.getenv("WEIGHT_SPECIALIST", 0.15))
    WEIGHT_PREDICTION = float(os.getenv("WEIGHT_PREDICTION", 0.10))
    WEIGHT_HISTORY = float(os.getenv("WEIGHT_HISTORY", 0.05))

    # Database
    DATABASE_PATH = os.path.join(os.path.dirname(__file__), "data", "hospital.db")

    # Average ambulance speed for ETA estimation (km/h)
    AVG_AMBULANCE_SPEED_KMH = 40
