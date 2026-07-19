"""
blackbird_enr.py — РЕАЛЬНЫЙ запуск Blackbird (p1ngul1n0/blackbird) по нику:
600+ сайтов (внутри тоже использует датасет WhatsMyName — как и наш username_sweep,
так что часть покрытия пересекается; ценность Blackbird здесь — независимый движок
проверки и AI-профилирование как доп. сигнал, а не замена нашего скоринга).

⚠️ Docker-only: ставится через git clone + pip install -r requirements.txt на
этапе сборки образа (см. Dockerfile) — не PyPI-пакет. На Vercel/без Docker —
энричер отдаёт факт «недоступно» и не падает.

Blackbird не имеет стабильного stdout-JSON API — пишет файл в свой results/.
Находим САМЫЙ СВЕЖИЙ .json там после запуска и парсим защитно (несколько
разумных вариантов имён полей), а не полагаемся на точную внутреннюю схему.
"""
import glob
import json
import os
import time

from ._binhelper import run
from .base import EnricherResult, enricher

TIMEOUT = int(os.getenv("BLACKBIRD_TIMEOUT", "120"))
REPO_DIR = os.getenv("BLACKBIRD_DIR", "/opt/blackbird")
# Ізольований venv (не системний python) — уникаємо конфлікту залежностей requirements.txt
# Blackbird з нашим власним web/scripts requirements (див. Dockerfile).
BLACKBIRD_PYTHON = os.getenv("BLACKBIRD_PYTHON", "/opt/blackbird/.venv/bin/python")
INSTALL_HINT = ("Docker-образ: git clone + venv (див. Dockerfile). Вручну: "
                "git clone https://github.com/p1ngul1n0/blackbird && pip install -r blackbird/requirements.txt")


def _newest_json(results_dir: str, since: float) -> dict | None:
    candidates = glob.glob(os.path.join(results_dir, "**", "*.json"), recursive=True)
    fresh = [c for c in candidates if os.path.getmtime(c) >= since]
    if not fresh:
        return None
    newest = max(fresh, key=os.path.getmtime)
    try:
        with open(newest, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    finally:
        try:
            os.remove(newest)
        except Exception:
            pass
    return data


def _extract_hits(data) -> list[dict]:
    """Защитно достать список найденных профилей из разных возможных форм JSON."""
    rows = data if isinstance(data, list) else (
        data.get("results") or data.get("sites") or data.get("accounts") or [])
    if not isinstance(rows, list):
        return []
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        found = r.get("found") if "found" in r else r.get("exists")
        if found is False:
            continue
        url = r.get("url") or r.get("uri") or r.get("link")
        site = r.get("site") or r.get("name") or r.get("platform") or "?"
        if not url:
            continue
        out.append({"site": site, "url": url})
    return out


@enricher("blackbird", "username")
def enrich_blackbird(value: str) -> EnricherResult:
    res = EnricherResult("blackbird", "username", value)
    u = value.strip().lstrip("@")
    root = res.node("username", u)

    binpath = BLACKBIRD_PYTHON if os.path.exists(BLACKBIRD_PYTHON) else None
    script = os.path.join(REPO_DIR, "blackbird.py")
    if not binpath or not os.path.exists(script):
        res.fact(f"Blackbird недоступний у цьому деплої (потрібен Docker-образ). "
                 f"Встановлення: {INSTALL_HINT}", "config")
        return res

    t0 = time.time()
    proc = run([binpath, script, "--username", u, "--json", "--no-update"],
              timeout=TIMEOUT, cwd=REPO_DIR)
    if proc is None:
        res.fact("Blackbird: таймаут або помилка запуску.", "blackbird")
        return res

    data = _newest_json(os.path.join(REPO_DIR, "results"), since=t0)
    if data is None:
        res.fact("Blackbird: не вдалося прочитати результат (файл не знайдено/некоректний JSON).",
                 "blackbird")
        return res

    hits = _extract_hits(data)
    for h in hits:
        n = res.node("url", h["url"], platform=h["site"], source="blackbird")
        res.edge(root, n, "profile_on")
        res.fact(f"{h['site']}: профіль існує — {h['url']}", "Blackbird", "D3")

    res.fact(f"Blackbird: знайдено {len(hits)} профілів (незалежний рушій перевірки, "
             f"частина покриття збігається з username_sweep).", "blackbird", "C3")
    return res
