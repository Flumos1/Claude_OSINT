"""
kv.py — тонкий клиент Upstash Redis по REST (для serverless-персистентности на Vercel).

На Vercel файловая система только для чтения, поэтому SQLite/файлы не персистятся между
инвокациями. Здесь — минимальный клиент Upstash Redis REST (HTTP, без сокетов/драйверов),
которым auth.py и cases_store.py пользуются, когда заданы переменные окружения:
  KV_REST_API_URL / KV_REST_API_TOKEN            (интеграция Vercel KV)
  или UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN (нативный Upstash)

Если их нет — kv_enabled() == False, и модули работают на локальном бэкенде (SQLite/файлы).
Локальный Docker/Render так остаётся полнофункциональным без внешних сервисов.
"""
import json
import os

import requests

TIMEOUT = 10


def _creds() -> tuple[str, str] | None:
    url = os.getenv("KV_REST_API_URL") or os.getenv("UPSTASH_REDIS_REST_URL")
    token = os.getenv("KV_REST_API_TOKEN") or os.getenv("UPSTASH_REDIS_REST_TOKEN")
    if url and token:
        return url.rstrip("/"), token
    return None


def kv_enabled() -> bool:
    return _creds() is not None


def cmd(*args):
    """Выполнить одну Redis-команду через REST. Возвращает поле result (или бросает)."""
    creds = _creds()
    if not creds:
        raise RuntimeError("KV не сконфигурирован (нет KV_REST_API_URL/TOKEN)")
    url, token = creds
    r = requests.post(url, headers={"Authorization": f"Bearer {token}"},
                      json=[str(a) for a in args], timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"KV error: {data['error']}")
    return data.get("result")


# — удобные обёртки —
def get(key: str):
    return cmd("GET", key)


def set(key: str, value: str, ex: int | None = None):
    return cmd("SET", key, value, "EX", ex) if ex else cmd("SET", key, value)


def delete(key: str):
    return cmd("DEL", key)


def exists(key: str) -> bool:
    return bool(cmd("EXISTS", key))


def incr(key: str) -> int:
    return int(cmd("INCR", key))


def sadd(key: str, member: str):
    return cmd("SADD", key, member)


def srem(key: str, member: str):
    return cmd("SREM", key, member)


def smembers(key: str) -> list[str]:
    return cmd("SMEMBERS", key) or []


def scard(key: str) -> int:
    return int(cmd("SCARD", key) or 0)


def rpush(key: str, value: str):
    return cmd("RPUSH", key, value)


def lrange(key: str, start: int = 0, stop: int = -1) -> list[str]:
    return cmd("LRANGE", key, start, stop) or []


def llen(key: str) -> int:
    return int(cmd("LLEN", key) or 0)


def get_json(key: str, default=None):
    v = get(key)
    return json.loads(v) if v else default


def set_json(key: str, obj, ex: int | None = None):
    return set(key, json.dumps(obj, ensure_ascii=False), ex=ex)
