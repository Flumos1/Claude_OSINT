"""
auth.py — мульти-юзер аутентификация на SQLite (stdlib, без внешних зависимостей).

Пользователи (роли admin/analyst), сессии-cookie. Пароли — PBKDF2-HMAC-SHA256.
БД в data/osint.db (data/ в .gitignore — чувствительно). Включается, когда есть
пользователи (сидинг админа из env OSINT_ADMIN_USER/OSINT_ADMIN_PASSWORD) или OSINT_AUTH=1.
"""
import hashlib
import hmac
import secrets
import sqlite3
import time
from pathlib import Path

_DB: Path | None = None
SESSION_TTL = 7 * 24 * 3600  # 7 дней


def init(db_path: Path) -> None:
    global _DB
    _DB = db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
            pw TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'analyst', created TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS sessions(
            token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires REAL NOT NULL)""")


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB)
    c.row_factory = sqlite3.Row
    return c


def _hash_pw(pw: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000)
    return f"200000${salt.hex()}${h.hex()}"


def _verify_pw(pw: str, stored: str) -> bool:
    try:
        iters, salt_hex, hash_hex = stored.split("$")
    except ValueError:
        return False
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt_hex), int(iters))
    return hmac.compare_digest(h.hex(), hash_hex)


def has_users() -> bool:
    with _conn() as c:
        return c.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None


def create_user(username: str, password: str, role: str = "analyst") -> dict:
    username = username.strip()
    if not username or not password:
        raise ValueError("Логин и пароль обязательны")
    if role not in ("admin", "analyst"):
        raise ValueError("Роль: admin или analyst")
    with _conn() as c:
        if c.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            raise ValueError("Пользователь уже существует")
        c.execute("INSERT INTO users(username, pw, role, created) VALUES(?,?,?,?)",
                  (username, _hash_pw(password), role, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
    return {"username": username, "role": role}


def seed_admin(username: str, password: str) -> None:
    """Создать админа, если пользователей ещё нет (идемпотентно)."""
    if not username or not password or has_users():
        return
    create_user(username, password, role="admin")


def verify_login(username: str, password: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE username=?", (username.strip(),)).fetchone()
    if row and _verify_pw(password, row["pw"]):
        return {"id": row["id"], "username": row["username"], "role": row["role"]}
    return None


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    with _conn() as c:
        c.execute("INSERT INTO sessions(token, user_id, expires) VALUES(?,?,?)",
                  (token, user_id, time.time() + SESSION_TTL))
    return token


def get_user_by_session(token: str) -> dict | None:
    if not token:
        return None
    with _conn() as c:
        row = c.execute("""SELECT u.id, u.username, u.role, s.expires FROM sessions s
                           JOIN users u ON u.id = s.user_id WHERE s.token=?""", (token,)).fetchone()
        if not row:
            return None
        if row["expires"] < time.time():
            c.execute("DELETE FROM sessions WHERE token=?", (token,))
            return None
    return {"id": row["id"], "username": row["username"], "role": row["role"]}


def delete_session(token: str) -> None:
    if token:
        with _conn() as c:
            c.execute("DELETE FROM sessions WHERE token=?", (token,))


def list_users() -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT username, role, created FROM users ORDER BY id").fetchall()
    return [dict(r) for r in rows]
