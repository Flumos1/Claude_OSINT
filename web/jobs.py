"""
jobs.py — простая очередь фоновых задач для долгих сканов (deep username 740 сайтов).

In-memory store + поток на джобу + queue для стрима прогресса (SSE). Стартово без
Redis/Celery — для локали достаточно; при деплое заменить store на внешний брокер
(см. web/ARCHITECTURE.md).
"""
import queue
import threading
import uuid

from enrichers.username_enr import stream_username  # из scripts (в sys.path добавлен в app.py)

# jid -> {"q": Queue, "status": running|done|error, "result": dict|None, "error": str|None}
JOBS: dict[str, dict] = {}

# тип джобы -> генератор событий
RUNNERS = {
    "username_deep": lambda value: stream_username(value, deep=True),
    "username_fast": lambda value: stream_username(value, deep=False),
}


def start(kind: str, value: str) -> str:
    if kind not in RUNNERS:
        raise ValueError(f"Неизвестный тип джобы: {kind}")
    jid = uuid.uuid4().hex[:12]
    JOBS[jid] = {"q": queue.Queue(), "status": "running", "result": None, "error": None}
    threading.Thread(target=_run, args=(jid, kind, value), daemon=True).start()
    return jid


def _run(jid: str, kind: str, value: str) -> None:
    job = JOBS[jid]
    q: queue.Queue = job["q"]
    try:
        for ev in RUNNERS[kind](value):
            if ev.get("event") == "done":
                job["result"] = ev.get("result")
                job["status"] = "done"
            q.put(ev)
    except Exception as e:  # noqa: BLE001
        job["status"] = "error"
        job["error"] = str(e)
        q.put({"event": "error", "error": str(e)})
    finally:
        q.put({"event": "end"})


def events(jid: str):
    """Блокирующий генератор событий джобы (для SSE). Завершается на 'end'."""
    job = JOBS.get(jid)
    if not job:
        return
    q: queue.Queue = job["q"]
    while True:
        ev = q.get()
        if ev.get("event") == "end":
            break
        yield ev


def status(jid: str) -> dict | None:
    job = JOBS.get(jid)
    if not job:
        return None
    return {"status": job["status"], "result": job["result"], "error": job["error"]}
