"""
auth.py — мульти-юзер аутентификация. Два бэкенда, единый API:
  • локально/Docker — SQLite (stdlib), БД в data/osint.db;
  • на Vercel (serverless, read-only ФС) — Upstash Redis KV (web/kv.py), когда заданы
    KV_REST_API_URL/TOKEN. Выбор автоматический по kv_enabled().

Пользователи (роли admin/analyst), сессии-cookie. Пароли — PBKDF2-HMAC-SHA256.
Включается, когда есть пользователи (сидинг админа из OSINT_ADMIN_USER/PASSWORD) или OSINT_AUTH=1.
"""
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from pathlib import Path

import kv

_DB: Path | None = None
SESSION_TTL = 7 * 24 * 3600  # 7 дней

# ── общее: хеширование ────────────────────────────────────────────────────────


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


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def init(db_path: Path) -> None:
    """Инициализация локального бэкенда (SQLite). На KV — no-op (ФС не трогаем)."""
    global _DB
    if kv.kv_enabled():
        return
    # На Vercel без KV файловая система read-only — уводим SQLite в /tmp (эфемерно,
    # не падаем при импорте). Для персистентности на Vercel настрой Upstash KV.
    if os.getenv("VERCEL") and not str(db_path).startswith("/tmp"):
        db_path = Path("/tmp") / db_path.name
    _DB = db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
            pw TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'analyst', created TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS sessions(
            token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires REAL NOT NULL)""")


# ── SQLite бэкенд ─────────────────────────────────────────────────────────────


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB)
    c.row_factory = sqlite3.Row
    return c


# ── KV бэкенд (ключи с префиксом osint:) ──────────────────────────────────────

_U = "osint:user:"     # osint:user:<username> -> {id,username,pw,role,created}
_USET = "osint:users"  # set имён
_UID = "osint:uid"     # счётчик id
_S = "osint:sess:"     # osint:sess:<token> -> {id,username,role}


# ── публичный API (диспетчер) ─────────────────────────────────────────────────


def has_users() -> bool:
    if kv.kv_enabled():
        return kv.scard(_USET) > 0
    with _conn() as c:
        return c.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None


def create_user(username: str, password: str, role: str = "analyst") -> dict:
    username = username.strip()
    if not username or not password:
        raise ValueError("Логин и пароль обязательны")
    if role not in ("admin", "analyst"):
        raise ValueError("Роль: admin или analyst")

    if kv.kv_enabled():
        if kv.exists(_U + username):
            raise ValueError("Пользователь уже существует")
        uid = kv.incr(_UID)
        kv.set_json(_U + username, {"id": uid, "username": username,
                                    "pw": _hash_pw(password), "role": role, "created": _now()})
        kv.sadd(_USET, username)
        return {"username": username, "role": role}

    with _conn() as c:
        if c.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            raise ValueError("Пользователь уже существует")
        c.execute("INSERT INTO users(username, pw, role, created) VALUES(?,?,?,?)",
                  (username, _hash_pw(password), role, _now()))
    return {"username": username, "role": role}


def seed_admin(username: str, password: str) -> None:
    """Создать админа, если пользователей ещё нет (идемпотентно)."""
    if not username or not password or has_users():
        return
    create_user(username, password, role="admin")


def verify_login(username: str, password: str) -> dict | None:
    username = username.strip()
    if kv.kv_enabled():
        u = kv.get_json(_U + username)
        if u and _verify_pw(password, u["pw"]):
            return {"id": u["id"], "username": u["username"], "role": u["role"]}
        return None
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if row and _verify_pw(password, row["pw"]):
        return {"id": row["id"], "username": row["username"], "role": row["role"]}
    return None


def create_session(user_id: int, user: dict | None = None) -> str:
    token = secrets.token_urlsafe(32)
    if kv.kv_enabled():
        u = user or {"id": user_id}
        kv.set_json(_S + token, {"id": u.get("id", user_id), "username": u.get("username", ""),
                                 "role": u.get("role", "analyst")}, ex=SESSION_TTL)
        return token
    with _conn() as c:
        c.execute("INSERT INTO sessions(token, user_id, expires) VALUES(?,?,?)",
                  (token, user_id, time.time() + SESSION_TTL))
    return token


def get_user_by_session(token: str) -> dict | None:
    if not token:
        return None
    if kv.kv_enabled():
        return kv.get_json(_S + token)  # None если истёк (EX) или нет
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
    if not token:
        return
    if kv.kv_enabled():
        kv.delete(_S + token)
        return
    with _conn() as c:
        c.execute("DELETE FROM sessions WHERE token=?", (token,))


def list_users() -> list[dict]:
    if kv.kv_enabled():
        out = []
        for name in sorted(kv.smembers(_USET)):
            u = kv.get_json(_U + name)
            if u:
                out.append({"username": u["username"], "role": u["role"], "created": u.get("created", "")})
        return out
    with _conn() as c:
        rows = c.execute("SELECT username, role, created FROM users ORDER BY id").fetchall()
    return [dict(r) for r in rows]
