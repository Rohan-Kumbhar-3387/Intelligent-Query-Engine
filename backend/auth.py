import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Tuple

DB_PATH = os.path.join(os.path.dirname(__file__), "users.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_auth_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                full_name TEXT,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                thread_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                sql TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)


def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        100000
    ).hex()
    return hashed, salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    new_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(new_hash, hashed)


def register_user(username: str, email: str, password: str, full_name: str = "") -> Tuple[Optional[dict], Optional[str]]:
    username = username.strip().lower()
    email = email.strip().lower()

    if not username or not email or not password:
        return None, "All fields are required."
    if len(password) < 6:
        return None, "Password must be at least 6 characters long."

    hashed_pw, salt = hash_password(password)

    try:
        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, email, full_name, password_hash, salt) VALUES (?, ?, ?, ?, ?)",
                (username, email, full_name.strip(), hashed_pw, salt)
            )
            user_id = cursor.lastrowid
            return {
                "id": user_id,
                "username": username,
                "email": email,
                "full_name": full_name.strip()
            }, None
    except sqlite3.IntegrityError as e:
        if "username" in str(e).lower():
            return None, "Username already taken."
        if "email" in str(e).lower():
            return None, "Email already registered."
        return None, "User with this username or email already exists."


def authenticate_user(login_identifier: str, password: str) -> Tuple[Optional[dict], Optional[str]]:
    identifier = login_identifier.strip().lower()
    if not identifier or not password:
        return None, "Please provide username/email and password."

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? OR email = ?",
            (identifier, identifier)
        ).fetchone()

        if not row:
            return None, "Invalid username or password."

        if not verify_password(password, row["password_hash"], row["salt"]):
            return None, "Invalid username or password."

        return {
            "id": row["id"],
            "username": row["username"],
            "email": row["email"],
            "full_name": row["full_name"]
        }, None


def create_session(user_id: int, hours_valid: int = 24) -> str:
    token = secrets.token_hex(32)
    expires_at = datetime.utcnow() + timedelta(hours=hours_valid)

    with get_db() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires_at.isoformat())
        )
    return token


def get_user_from_session(token: str) -> Optional[dict]:
    if not token:
        return None

    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        row = conn.execute("""
            SELECT u.id, u.username, u.email, u.full_name
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ? AND s.expires_at > ?
        """, (token, now)).fetchone()

        if row:
            return dict(row)
    return None


def destroy_session(token: str):
    if not token:
        return
    with get_db() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


def save_chat_turn(user_id: int, thread_id: str, role: str, content: str, sql: Optional[str] = None):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO conversation_history (user_id, thread_id, role, content, sql) VALUES (?, ?, ?, ?, ?)",
            (user_id, thread_id, role, content, sql)
        )


def get_chat_history(user_id: int, thread_id: str, limit: int = 50) -> list:
    with get_db() as conn:
        rows = conn.execute("""
            SELECT role, content, sql, created_at
            FROM conversation_history
            WHERE user_id = ? AND thread_id = ?
            ORDER BY id ASC
            LIMIT ?
        """, (user_id, thread_id, limit)).fetchall()
        return [dict(r) for r in rows]


def clear_chat_history(user_id: int, thread_id: str):
    with get_db() as conn:
        conn.execute(
            "DELETE FROM conversation_history WHERE user_id = ? AND thread_id = ?",
            (user_id, thread_id)
        )


# Initialize database tables on import
init_auth_db()
