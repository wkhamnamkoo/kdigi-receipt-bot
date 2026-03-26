"""
auth.py — ระบบ Login / Session สำหรับ K-Digi Dashboard
- Hash password ด้วย SHA-256 + salt
- Session token เก็บใน memory (single-server)
- Role: admin / support
"""
import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

DB_PATH = "kdigi_logs.db"
SESSION_HOURS = 8

# { token: { user_id, username, display_name, role, expires_at } }
_sessions: dict = {}


# ── Password helpers ───────────────────────────────────────────

def hash_password(password: str, salt: str = "") -> str:
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}:{hashed}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, _ = stored.split(":", 1)
        return hash_password(password, salt) == stored
    except Exception:
        return False


# ── User management ───────────────────────────────────────────

def init_users_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT UNIQUE NOT NULL,
            password     TEXT NOT NULL,
            display_name TEXT NOT NULL,
            role         TEXT DEFAULT 'support',
            is_active    INTEGER DEFAULT 1,
            created_at   TEXT,
            last_login   TEXT
        )
    """)
    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        conn.execute(
            "INSERT INTO users (username, password, display_name, role, created_at) VALUES (?,?,?,?,?)",
            ("admin", hash_password("kdigi2024"), "ผู้ดูแลระบบ", "admin",
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        print("✅ สร้าง admin เริ่มต้นแล้ว (username: admin / password: kdigi2024)")
    conn.close()


def get_user(username: str) -> Optional[dict]:
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM users WHERE username=? AND is_active=1", (username,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        print(f"get_user error: {e}")
        return None


def get_all_users() -> list:
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, username, display_name, role, is_active, created_at, last_login "
            "FROM users ORDER BY id"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"get_all_users error: {e}")
        return []


def create_user(username: str, password: str, display_name: str, role: str = "support") -> dict:
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO users (username, password, display_name, role, created_at) VALUES (?,?,?,?,?)",
            (username, hash_password(password), display_name, role,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        conn.close()
        return {"status": "ok"}
    except sqlite3.IntegrityError:
        return {"status": "error", "detail": "username นี้มีอยู่แล้ว"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def update_user(user_id: int, display_name: str, role: str,
                is_active: int, new_password: str = "") -> dict:
    try:
        conn = sqlite3.connect(DB_PATH)
        if new_password.strip():
            conn.execute(
                "UPDATE users SET display_name=?, role=?, is_active=?, password=? WHERE id=?",
                (display_name, role, is_active, hash_password(new_password), user_id)
            )
        else:
            conn.execute(
                "UPDATE users SET display_name=?, role=?, is_active=? WHERE id=?",
                (display_name, role, is_active, user_id)
            )
        conn.commit()
        conn.close()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def delete_user(user_id: int) -> dict:
    """Soft delete — set is_active=0"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE users SET is_active=0 WHERE id=?", (user_id,))
        conn.commit()
        conn.close()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


deactivate_user = delete_user


# ── Session management ────────────────────────────────────────

def login(username: str, password: str) -> Optional[str]:
    """ตรวจสอบ username/password แล้วสร้าง session token"""
    user = get_user(username)
    if not user or not verify_password(password, user["password"]):
        return None

    token = secrets.token_urlsafe(32)
    _sessions[token] = {
        "user_id":      user["id"],
        "username":     user["username"],
        "display_name": user["display_name"],
        "role":         user["role"],
        "expires_at":   datetime.now() + timedelta(hours=SESSION_HOURS),
    }

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "UPDATE users SET last_login=? WHERE id=?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user["id"])
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

    return token


def get_session(token: str) -> Optional[dict]:
    if not token:
        return None
    session = _sessions.get(token)
    if not session:
        return None
    if datetime.now() > session["expires_at"]:
        del _sessions[token]
        return None
    return session


def logout(token: str):
    _sessions.pop(token, None)


def get_session_from_request(request) -> Optional[dict]:
    token = request.cookies.get("kdigi_token", "")
    return get_session(token)


def require_login(request) -> Optional[dict]:
    return get_session_from_request(request)


def require_admin(request) -> Optional[dict]:
    session = get_session_from_request(request)
    if not session or session.get("role") != "admin":
        return None
    return session
