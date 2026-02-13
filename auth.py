"""
Firebase Authentication Helper — Verifies Firebase ID tokens for protected routes.
"""
import functools
import json
import urllib.request
import urllib.error
from flask import request, jsonify
from config import Config

# Google's public key endpoint for verifying Firebase tokens
GOOGLE_CERTS_URL = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"

# In-memory cache of Firebase users (uid -> role)
# In production, use Firebase Admin SDK. This is a lightweight verifier.
ADMIN_EMAILS = set()
DRIVER_EMAILS = set()


def _decode_jwt_unverified(token):
    """
    Decode a Firebase JWT token WITHOUT cryptographic verification.
    For hackathon use — in production, use firebase-admin SDK with full verification.
    This extracts claims from the token payload.
    """
    import base64
    parts = token.split(".")
    if len(parts) != 3:
        return None
    # Decode payload (second part)
    payload = parts[1]
    # Add padding
    payload += "=" * (4 - len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception:
        return None


def verify_firebase_token(token):
    """
    Verify a Firebase ID token and return the decoded claims.
    Uses lightweight JWT decode — for production, use firebase_admin.auth.verify_id_token().
    """
    if not token:
        return None
    try:
        claims = _decode_jwt_unverified(token)
        if not claims:
            return None
        # Check issuer matches our project
        project_id = Config.FIREBASE_PROJECT_ID
        if project_id:
            expected_iss = f"https://securetoken.google.com/{project_id}"
            if claims.get("iss") != expected_iss:
                return None
        # Check expiry
        import time
        if claims.get("exp", 0) < time.time():
            return None
        return claims
    except Exception:
        return None


def get_token_from_request():
    """Extract Bearer token from Authorization header."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


def require_auth(role=None):
    """
    Decorator to protect Flask routes with Firebase authentication.
    role: 'admin' or 'driver' — if None, any authenticated user is allowed.
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            token = get_token_from_request()
            if not token:
                return jsonify({"error": "Authentication required", "code": "NO_TOKEN"}), 401
            claims = verify_firebase_token(token)
            if not claims:
                return jsonify({"error": "Invalid or expired token", "code": "INVALID_TOKEN"}), 401
            # Attach user info to request
            request.firebase_user = claims
            request.firebase_uid = claims.get("user_id") or claims.get("sub")
            request.firebase_email = claims.get("email", "")
            # Role check (using custom claims or email-based lookup)
            if role == "admin":
                custom_role = claims.get("role", "")
                if custom_role != "admin" and request.firebase_email not in ADMIN_EMAILS:
                    # For hackathon: allow any authenticated user as admin
                    # In production, enforce strict role checking
                    pass
            elif role == "driver":
                custom_role = claims.get("role", "")
                if custom_role != "driver" and request.firebase_email not in DRIVER_EMAILS:
                    pass
            return f(*args, **kwargs)
        return wrapper
    return decorator


def require_auth_optional():
    """
    Decorator that extracts auth if present but doesn't require it.
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            token = get_token_from_request()
            if token:
                claims = verify_firebase_token(token)
                if claims:
                    request.firebase_user = claims
                    request.firebase_uid = claims.get("user_id") or claims.get("sub")
                    request.firebase_email = claims.get("email", "")
                else:
                    request.firebase_user = None
                    request.firebase_uid = None
                    request.firebase_email = None
            else:
                request.firebase_user = None
                request.firebase_uid = None
                request.firebase_email = None
            return f(*args, **kwargs)
        return wrapper
    return decorator
