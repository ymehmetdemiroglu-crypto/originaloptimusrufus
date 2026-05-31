"""Admin authentication middleware.

Protects /api/admin/* routes with a simple API key check or secure session cookie.
"""
import os
import hashlib
import binascii
import secrets
import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Request, HTTPException, Depends
from fastapi.security import APIKeyHeader

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")

if not ADMIN_PASSWORD_HASH and not ADMIN_PASSWORD:
    logging.warning("Admin auth is disabled: neither ADMIN_PASSWORD_HASH nor ADMIN_PASSWORD is set")

# Thread safety lock
_auth_lock = threading.Lock()

# Simple session token store (in production, use Redis or DB)
_active_sessions: dict[str, datetime] = {}
SESSION_TTL_HOURS = 24

# Lockout configurations
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = 900  # 15 minutes (900 seconds)
_failed_login_attempts: dict[str, list[float]] = {}  # ip -> failure timestamps

api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


# ---------------------------------------------------------------------------
# Password hashing helpers
# ---------------------------------------------------------------------------

def hash_password(password: str, salt: str = None) -> str:
    """Generate a PBKDF2 SHA256 hashed password string: pbkdf2_sha256$<iterations>$<salt>$<hash>"""
    iterations = 100000
    if salt is None:
        salt = binascii.hexlify(os.urandom(16)).decode('ascii')
    
    dk = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        iterations
    )
    hex_hash = binascii.hexlify(dk).decode('ascii')
    return f"pbkdf2_sha256${iterations}${salt}${hex_hash}"


def verify_hashed_password(password: str, hashed: str) -> bool:
    """Verifies a password against a pbkdf2_sha256 hash or fallback plaintext."""
    if not hashed:
        return False
        
    if hashed.startswith("pbkdf2_sha256$"):
        try:
            parts = hashed.split("$")
            iterations = int(parts[1])
            salt = parts[2]
            stored_hash = parts[3]
            
            dk = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt.encode('utf-8'),
                iterations
            )
            computed_hash = binascii.hexlify(dk).decode('ascii')
            return secrets.compare_digest(stored_hash, computed_hash)
        except Exception:
            logging.exception("Error verifying password hash")
            return False
            
    # Reject non-pbkdf2 hashes
    return False


def verify_password(password: str) -> bool:
    """Verify admin password using secure hash verification."""
    # Explicitly reject if no credentials are configured
    if not ADMIN_PASSWORD_HASH and not ADMIN_PASSWORD:
        return False
    
    # 1. Check if hashed password is provided
    if ADMIN_PASSWORD_HASH:
        return verify_hashed_password(password, ADMIN_PASSWORD_HASH)
    
    # 2. Fallback to check plain password (which may contain a plain text or a hash value)
    if ADMIN_PASSWORD:
        return verify_hashed_password(password, ADMIN_PASSWORD)
        
    return False


# ---------------------------------------------------------------------------
# Rate limiting & Lockout helpers
# ---------------------------------------------------------------------------

def check_rate_limit(ip: str) -> bool:
    """Returns True if the IP is allowed to attempt login, False if locked out."""
    now = time.time()
    with _auth_lock:
        if ip not in _failed_login_attempts:
            return True
        
        # Filter failures within lockout window
        attempts = [t for t in _failed_login_attempts[ip] if now - t < LOCKOUT_DURATION]
        _failed_login_attempts[ip] = attempts
        
        if len(attempts) >= MAX_FAILED_ATTEMPTS:
            return False
        return True


def record_failed_attempt(ip: str):
    """Records a failed attempt for the given IP."""
    now = time.time()
    with _auth_lock:
        if ip not in _failed_login_attempts:
            _failed_login_attempts[ip] = []
        _failed_login_attempts[ip].append(now)


def clear_failed_attempts(ip: str):
    """Clears failed attempts for the given IP."""
    with _auth_lock:
        _failed_login_attempts.pop(ip, None)


# ---------------------------------------------------------------------------
# Session management helpers
# ---------------------------------------------------------------------------

def cleanup_expired_sessions():
    """Removes all expired sessions from memory."""
    now = datetime.utcnow()
    with _auth_lock:
        expired = [token for token, expires in _active_sessions.items() if now >= expires]
        for token in expired:
            _active_sessions.pop(token, None)


async def require_admin(request: Request, api_key: Optional[str] = Depends(api_key_header)):
    """Dependency that enforces admin authentication.
    
    Accepts either:
    - X-Admin-Key header matching ADMIN_API_KEY
    - admin_token cookie with a valid session token
    """
    # Periodic cleanup of expired sessions to prevent memory leak
    cleanup_expired_sessions()

    # Method 1: API key header
    if api_key and ADMIN_API_KEY and secrets.compare_digest(api_key.encode('utf-8'), ADMIN_API_KEY.encode('utf-8')):
        return True
    
    # Method 2: Session cookie
    session_token = request.cookies.get("admin_token")
    if session_token:
        with _auth_lock:
            if session_token in _active_sessions:
                expires = _active_sessions[session_token]
                if datetime.utcnow() < expires:
                    return True
                else:
                    # Expired session
                    _active_sessions.pop(session_token, None)
    
    raise HTTPException(status_code=401, detail="Unauthorized — admin access required")


def create_session() -> str:
    """Create a new admin session token. Returns the token."""
    cleanup_expired_sessions()
    token = secrets.token_urlsafe(32)
    with _auth_lock:
        _active_sessions[token] = datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS)
    return token


def invalidate_session(token: str):
    """Invalidate a session token."""
    with _auth_lock:
        _active_sessions.pop(token, None)
