#!/usr/bin/env python3
"""
Claude OSINT — веб-оболочка (FastAPI) поверх движка энричеров.

Запуск:
    cd "G:\\Claude OSINT\\web"
    python -m pip install -r requirements.txt
    python app.py                     # http://127.0.0.1:8000

Назначение: единый интерфейс к workspace — дашборд, запуск энричеров (сущность → граф),
источники по странам, скилы-плейбуки, кейсы. Локально, без внешних зависимостей рантайма.
"""
import json
import re
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
KNOWLEDGE = ROOT / "knowledge"
SOURCES = KNOWLEDGE / "sources"
SKILLS = ROOT / ".claude" / "skills"
CASES = ROOT / "cases"
STATIC = Path(__file__).resolve().parent / "static"

# движок энричеров
sys.path.insert(0, str(SCRIPTS))
from enrich import run as enrich_run  # noqa: E402
from enrichers.base import ENTITY_TYPES, REGISTRY  # noqa: E402
from person_search import dossier_to_markdown, search_person  # noqa: E402
import jobs as jobq  # noqa: E402

try:
    import markdown as md
except ImportError:
    md = None

app = FastAPI(title="Claude OSINT", docs_url="/api/docs")

COUNTRY_META = {
    "ua": {"flag": "🇺🇦", "name": "Україна", "priority": True},
    "ru": {"flag": "🇷🇺", "name": "Россия"},
    "intl": {"flag": "🌍", "name": "International"},
}


def _frontmatter(text: str) -> dict:
    """Парсит YAML-ish frontmatter (name/description) из SKILL.md."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    out = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line and not line.startswith(" "):
                k, _, v = line.partition(":")
                out[k.strip()] = v.strip()
    return out


@app.get("/api/meta")
def meta():
    enrichers = {}
    for t, items in REGISTRY.items():
        enrichers[t] = [{"name": n, "country": c} for n, _, c in items]
    countries = []
    for f in SOURCES.glob("*.md"):
        code = f.stem
        if code.startswith("_") or code == "README":
            continue
        cm = COUNTRY_META.get(code, {"flag": "🏳️", "name": code.upper()})
        countries.append({"code": code, **cm})
    # приоритетные (UA) первыми, дальше по алфавиту
    countries.sort(key=lambda c: (not c.get("priority"), c["code"]))
    skills = len([d for d in SKILLS.glob("*") if (d / "SKILL.md").exists()])
    cases = len([d for d in CASES.glob("*") if d.is_dir() and not d.name.startswith("_")])
    tools_total = 0
    ti = KNOWLEDGE / "tools-index.json"
    if ti.exists():
        try:
            tools_total = json.loads(ti.read_text(encoding="utf-8")).get("total_tools", 0)
        except Exception:
            pass
    return {
        "enrichers": enrichers,
        "entity_types": sorted(ENTITY_TYPES),
        "countries": countries,
        "counts": {
            "enrichers": sum(len(v) for v in REGISTRY.values()),
            "entity_types": len(ENTITY_TYPES),
            "countries": len(countries),
            "skills": skills,
            "cases": cases,
            "tools": tools_total,
        },
    }


class EnrichReq(BaseModel):
    type: str
    value: str
    country: str | None = "ua"


@app.post("/api/enrich")
def api_enrich(req: EnrichReq):
    if req.type not in ENTITY_TYPES:
        raise HTTPException(400, f"Неизвестный тип: {req.type}")
    if not req.value.strip():
        raise HTTPException(400, "Пустое значение")
    return enrich_run(req.type, req.value.strip(), req.country)


# --- Каталог инструментов (индекс awesome-osint, 1400+) ---------------------

# Эвристические этик-флаги: наличие в индексе ≠ одобрение (см. ethics-legal.md).
_CAUTION_KW = {
    "деанон": "деанонимизация", "deanon": "деанонимизация", "doxx": "доксинг",
    "dox ": "доксинг", "докс": "доксинг", "пробив": "«пробив» по закрытым данным",
    "stealer": "кража учётных данных", "grabber": "грабер токенов",
    "ghosttrack": "трекинг лица", "phonetrack": "трекинг телефона",
    "geolocation track": "трекинг локации", "ip logger": "скрытый логгер IP",
    "bypass": "обход защиты/ToS", "captcha solv": "обход капчи",
    "anti-bot": "обход анти-бота", "combolist": "комболисты (слитые пары)",
    "leaked database": "торговля слитыми базами",
}

_TOOLS_CACHE: dict | None = None


def _load_tools() -> dict:
    global _TOOLS_CACHE
    if _TOOLS_CACHE is not None:
        return _TOOLS_CACHE
    ti = KNOWLEDGE / "tools-index.json"
    items: list[dict] = []
    cats: dict[str, int] = {}
    if ti.exists():
        data = json.loads(ti.read_text(encoding="utf-8"))
        for s in data.get("sections", []):
            cat = s.get("category", "—")
            for t in s.get("tools", []):
                hay = f"{t.get('name','')} {t.get('desc','')}".lower()
                flag = None
                for kw, reason in _CAUTION_KW.items():
                    if kw in hay:
                        flag = reason
                        break
                items.append({"name": t.get("name", ""), "url": t.get("url", ""),
                              "desc": t.get("desc", ""), "category": cat, "flag": flag})
                cats[cat] = cats.get(cat, 0) + 1
    _TOOLS_CACHE = {"items": items, "categories": cats}
    return _TOOLS_CACHE


@app.get("/api/tools")
def api_tools(q: str = "", category: str = "", flagged: bool = False,
              limit: int = 60, offset: int = 0):
    data = _load_tools()
    items = data["items"]
    ql = q.strip().lower()
    if ql:
        items = [t for t in items if ql in t["name"].lower() or ql in t["desc"].lower()]
    if category:
        items = [t for t in items if t["category"] == category]
    if flagged:
        items = [t for t in items if t["flag"]]
    total = len(items)
    cats = sorted(({"name": c, "count": n} for c, n in data["categories"].items()),
                  key=lambda x: -x["count"])
    return {
        "total": total,
        "all_total": len(data["items"]),
        "flagged_total": sum(1 for t in data["items"] if t["flag"]),
        "categories": cats,
        "items": items[offset:offset + limit],
    }


class JobReq(BaseModel):
    kind: str          # username_deep | username_fast
    value: str


@app.post("/api/jobs")
def api_job_start(req: JobReq):
    if not req.value.strip():
        raise HTTPException(400, "Пустое значение")
    try:
        jid = jobq.start(req.kind, req.value.strip())
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"id": jid}


@app.get("/api/jobs/{jid}")
def api_job_status(jid: str):
    st = jobq.status(jid)
    if st is None:
        raise HTTPException(404, "Джоба не найдена")
    return st


@app.get("/api/jobs/{jid}/stream")
def api_job_stream(jid: str):
    if jobq.status(jid) is None:
        raise HTTPException(404, "Джоба не найдена")

    def gen():
        for ev in jobq.events(jid):
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


class PersonReq(BaseModel):
    name: str
    dob: str | None = None
    rnokpp: str | None = None
    email: str | None = None
    phone: str | None = None
    username: str | None = None
    countries: list[str] = ["ua", "ru", "intl"]


@app.post("/api/person")
def api_person(req: PersonReq):
    if not req.name.strip():
        raise HTTPException(400, "Пустое ФИО")
    return search_person(req.name.strip(), req.dob, req.rnokpp, req.email or None,
                         req.phone or None, req.username or None, tuple(req.countries))


@app.post("/api/person/report")
def api_person_report(req: PersonReq):
    if not req.name.strip():
        raise HTTPException(400, "Пустое ФИО")
    d = search_person(req.name.strip(), req.dob, req.rnokpp, req.email or None,
                      req.phone or None, req.username or None, tuple(req.countries))
    return JSONResponse({"markdown": dossier_to_markdown(d)})


@app.get("/api/sources/{code}")
def api_source(code: str):
    f = SOURCES / f"{code}.md"
    if not f.exists() or ".." in code or "/" in code:
        raise HTTPException(404, "Источник не найден")
    text = f.read_text(encoding="utf-8")
    html = md.markdown(text, extensions=["tables", "fenced_code"]) if md else f"<pre>{text}</pre>"
    return {"code": code, "html": html}


@app.get("/api/skills")
def api_skills():
    out = []
    for d in sorted(SKILLS.glob("*")):
        sf = d / "SKILL.md"
        if sf.exists():
            fm = _frontmatter(sf.read_text(encoding="utf-8"))
            out.append({"name": fm.get("name", d.name), "description": fm.get("description", "")})
    return out


@app.get("/api/cases")
def api_cases():
    out = []
    for d in sorted(CASES.glob("*")):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        brief = ""
        bf = d / "00-brief.md"
        if bf.exists():
            brief = bf.read_text(encoding="utf-8")[:400]
        out.append({"slug": d.name, "brief": brief})
    return out


@app.get("/")
def index():
    # Новый UI (React/Vite) если собран, иначе — текущая SPA
    dist_index = STATIC / "dist" / "index.html"
    if dist_index.exists():
        return RedirectResponse("/app/")
    return FileResponse(STATIC / "index.html")


@app.get("/legacy")
def legacy():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

# Новый фронтенд (React/Vite) — собирается в static/dist (npm run build в web/ui)
_DIST = STATIC / "dist"
if _DIST.exists():
    app.mount("/app", StaticFiles(directory=str(_DIST), html=True), name="app")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
