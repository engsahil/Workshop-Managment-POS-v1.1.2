"""Password hashing (Argon2 with bcrypt fallback) and JWT token handling."""
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..core.config import APP_ROOT, ACCESS_TOKEN_EXPIRE_MINUTES, DATA_DIR, SECRET_KEY

try:
    from argon2 import PasswordHasher, exceptions as _argon_exc
    _HAS_ARGON2 = True
except Exception:  # pragma: no cover
    _HAS_ARGON2 = False

try:
    import bcrypt as _bcrypt
    _HAS_BCRYPT = True
except Exception:  # pragma: no cover
    _HAS_BCRYPT = False

import jwt


# ---------- password hashing ----------
_argon = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2) if _HAS_ARGON2 else None


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password must not be empty")
    if _argon is not None:
        return _argon.hash(password)
    if _HAS_BCRYPT:
        return "bcrypt$" + _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()
    # Last-resort PBKDF2 (still salted + stretched)
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return f"pbkdf2${salt}${dk.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    if not password or not password_hash:
        return False
    try:
        if password_hash.startswith("$argon2"):
            if _argon is not None:
                return _argon.verify(password_hash, password)
            return False
        if password_hash.startswith("bcrypt$"):
            if _HAS_BCRYPT:
                return _bcrypt.checkpw(password.encode(), password_hash[7:].encode())
            return False
        if password_hash.startswith("pbkdf2$"):
            _, salt, want = password_hash.split("$")
            dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
            return hmac.compare_digest(dk.hex(), want)
    except Exception:
        return False
    return False


# ---------- JWT ----------
def _secret() -> str:
    if SECRET_KEY:
        return SECRET_KEY
    # persist a generated secret on first run (server-side only, never exposed to clients)
    f = DATA_DIR / ".jwt_secret"
    try:
        if f.exists():
            return f.read_text().strip()
        key = secrets.token_urlsafe(48)
        f.write_text(key)
        f.chmod(0o600)
        return key
    except OSError:
        return "dev-insecure-secret-change-me"


def create_token(user_id: int, username: str, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }
    return jwt.encode(payload, _secret(), algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, _secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return {"expired": True}
    except jwt.InvalidTokenError:
        return None


def token_expired(payload: dict) -> bool:
    return bool(payload.get("expired"))


# ---------- misc ----------
def utcnow() -> datetime:
    return datetime.now(timezone.utc)
