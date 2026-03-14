"""
User profile storage for EduNova.
Primary: Google Cloud Firestore (persistent, durable).
Fallback: Local JSON file (for local dev without Firestore).
Passwords are hashed with bcrypt before storage.
"""

import hashlib
import hmac
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
USERS_FILE = DATA_DIR / "users.json"

# ---------------------------------------------------------------------------
# Password hashing (using hashlib + salt — no extra dependency needed)
# ---------------------------------------------------------------------------

def _hash_password(password: str) -> str:
    """Hash a password with a random salt using SHA-256."""
    salt = os.urandom(16).hex()
    pw_hash = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${pw_hash}"


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored salt$hash string."""
    if "$" not in stored_hash:
        return False
    salt, pw_hash = stored_hash.split("$", 1)
    return hmac.compare_digest(
        hashlib.sha256((salt + password).encode("utf-8")).hexdigest(),
        pw_hash,
    )

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
USERS_FILE = DATA_DIR / "users.json"

# ---------------------------------------------------------------------------
# Firestore client (lazy-init singleton)
# ---------------------------------------------------------------------------
_firestore_db = None
_firestore_available: Optional[bool] = None
COLLECTION = "edunova_users"


def _get_firestore():
    """Return a Firestore client if available, else None."""
    global _firestore_db, _firestore_available
    if _firestore_available is False:
        return None
    if _firestore_db is not None:
        return _firestore_db
    try:
        from google.cloud import firestore  # type: ignore
        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        _firestore_db = firestore.Client(project=project) if project else firestore.Client()
        _firestore_available = True
        logger.info("Firestore client initialized successfully")
        return _firestore_db
    except Exception as e:
        _firestore_available = False
        logger.warning(f"Firestore not available, using local JSON fallback: {e}")
        return None


# ---------------------------------------------------------------------------
# Local JSON helpers (fallback)
# ---------------------------------------------------------------------------
def _ensure_file() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not USERS_FILE.exists():
        USERS_FILE.write_text("[]", encoding="utf-8")


def _load_users() -> list[dict]:
    _ensure_file()
    try:
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _save_users(users: list[dict]) -> None:
    _ensure_file()
    USERS_FILE.write_text(json.dumps(users, indent=2, default=str), encoding="utf-8")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def save_user(profile: dict) -> dict:
    """Save a new user profile and return it with a generated id.

    Raises ValueError if the username is already taken.
    """
    username = profile.get("username", "").strip().lower()
    password = profile.get("password", "")

    if not username or len(username) < 3:
        raise ValueError("Username must be at least 3 characters")
    if not password or len(password) < 6:
        raise ValueError("Password must be at least 6 characters")

    # Check for duplicate username
    if get_user_by_username(username) is not None:
        raise ValueError("Username already taken")

    user_id = str(uuid.uuid4())[:8]
    record = {
        "id": user_id,
        "username": username,
        "password_hash": _hash_password(password),
        "name": profile.get("name", "").strip(),
        "gender": profile.get("gender", "").strip().lower(),
        "grade": profile.get("grade", ""),
        "age": profile.get("age", ""),
        "language": profile.get("language", "en"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Try Firestore first
    db = _get_firestore()
    if db is not None:
        try:
            db.collection(COLLECTION).document(user_id).set(record)
            logger.info(f"User saved to Firestore: {record['name']} (id={user_id})")
            return _safe_record(record)
        except Exception as e:
            logger.error(f"Firestore write failed, falling back to JSON: {e}")

    # Fallback to local JSON
    users = _load_users()
    users.append(record)
    _save_users(users)
    logger.info(f"User saved to local JSON: {record['name']} (id={user_id})")

    return _safe_record(record)


def login_user(username: str, password: str) -> Optional[dict]:
    """Authenticate a user by username and password.

    Returns the user record (without password_hash) on success, None on failure.
    """
    username = username.strip().lower()
    user = get_user_by_username(username)
    if user is None:
        return None
    if not _verify_password(password, user.get("password_hash", "")):
        return None
    return _safe_record(user)


def get_user_by_username(username: str) -> Optional[dict]:
    """Look up a user by username."""
    username = username.strip().lower()

    db = _get_firestore()
    if db is not None:
        try:
            docs = (
                db.collection(COLLECTION)
                .where("username", "==", username)
                .limit(1)
                .stream()
            )
            for doc in docs:
                return doc.to_dict()
        except Exception:
            pass

    # Fallback
    for u in _load_users():
        if u.get("username", "").lower() == username:
            return u
    return None


def _safe_record(record: dict) -> dict:
    """Return a copy of the record without the password hash."""
    safe = {k: v for k, v in record.items() if k != "password_hash"}
    return safe


def get_user(user_id: str) -> Optional[dict]:
    """Retrieve a user by id."""
    db = _get_firestore()
    if db is not None:
        try:
            doc = db.collection(COLLECTION).document(user_id).get()
            if doc.exists:
                return _safe_record(doc.to_dict())
        except Exception:
            pass

    # Fallback
    for u in _load_users():
        if u.get("id") == user_id:
            return _safe_record(u)
    return None


def get_all_users() -> list[dict]:
    """Return all registered users."""
    db = _get_firestore()
    if db is not None:
        try:
            docs = db.collection(COLLECTION).order_by("created_at").stream()
            return [_safe_record(doc.to_dict()) for doc in docs]
        except Exception:
            pass

    return [_safe_record(u) for u in _load_users()]
