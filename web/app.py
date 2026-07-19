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
import os
import re
import sys
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse,
                               RedirectResponse, Response, StreamingResponse)
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
from person_recon import build as recon_build, report_markdown as recon_markdown  # noqa: E402
import osint_graph as OG  # noqa: E402
from docx_lite import markdown_to_docx  # noqa: E402
import jobs as jobq  # noqa: E402
import cases_store as cstore  # noqa: E402


def _report_response(markdown: str, fmt: str, filename: str):
    """Отдать отчёт: md (JSON), docx (файл на stdlib), html (JSON для печати→PDF)."""
    fmt = (fmt or "md").lower()
    if fmt == "docx":
        return Response(content=markdown_to_docx(markdown),
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": f'attachment; filename="{filename}.docx"'})
    if fmt == "html":
        body = md.markdown(markdown, extensions=["tables", "fenced_code"]) if md else f"<pre>{markdown}</pre>"
        return JSONResponse({"html": body, "filename": filename})
    return JSONResponse({"markdown": markdown, "filename": filename})

try:
    import markdown as md
except ImportError:
    md = None

app = FastAPI(title="Claude OSINT", docs_url="/api/docs")

# --- Аутентификация (мульти-юзер на SQLite + опц. API-токен) ----------------
import auth as authmod  # noqa: E402

authmod.init(ROOT / "data" / "osint.db")
authmod.seed_admin(os.getenv("OSINT_ADMIN_USER", "admin"),
                   os.getenv("OSINT_ADMIN_PASSWORD", "").strip())
OSINT_TOKEN = os.getenv("OSINT_TOKEN", "").strip()  # fallback для API-клиентов


def _auth_enabled() -> bool:
    return os.getenv("OSINT_AUTH", "").lower() in ("1", "true", "yes") or authmod.has_users()


def _current_user(request: Request) -> dict | None:
    return authmod.get_user_by_session(request.cookies.get("osint_session", ""))


def _require_admin(request: Request) -> dict:
    u = _current_user(request)
    if not u or u.get("role") != "admin":
        raise HTTPException(403, "Только для администратора")
    return u


_LOGIN_HTML = """<!doctype html><html lang=ru><meta charset=utf-8>
<title>Claude OSINT — вход</title>
<style>body{{font-family:Inter,system-ui,sans-serif;background:#0d1117;color:#e6edf3;
display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}}
form{{background:#161b22;border:1px solid #272e3a;border-radius:12px;padding:28px;width:300px}}
input{{width:100%;padding:9px 12px;margin:8px 0;background:#0d1117;border:1px solid #272e3a;
border-radius:8px;color:#e6edf3;font-size:14px;box-sizing:border-box}}
button{{width:100%;padding:10px;margin-top:6px;background:#4c8dff;color:#fff;border:0;border-radius:8px;
font-size:14px;cursor:pointer}}h1{{font-size:16px;margin:0 0 4px}}p{{color:#9aa7b5;font-size:12px;margin:0}}
.err{{color:#f85149;font-size:12px}}</style>
<form method=post action=/login><h1>Claude OSINT</h1>
<p>Вход в платформу</p>{err}
<input name=username placeholder=логин autofocus autocomplete=username>
<input type=password name=password placeholder=пароль autocomplete=current-password>
<button type=submit>Войти</button></form></html>"""


@app.middleware("http")
async def _auth(request: Request, call_next):
    path = request.url.path
    if _auth_enabled() and path.startswith("/api") and path != "/api/auth/login":
        ok = bool(_current_user(request))
        if not ok and OSINT_TOKEN and request.headers.get("X-Token") == OSINT_TOKEN:
            ok = True
        if not ok:
            return JSONResponse({"detail": "Не авторизован"}, status_code=401)
    return await call_next(request)


@app.get("/login", response_class=HTMLResponse)
def login_form():
    return _LOGIN_HTML.format(err="")


@app.post("/login")
def login_submit(username: str = Form(""), password: str = Form("")):
    user = authmod.verify_login(username, password)
    if not user:
        return HTMLResponse(_LOGIN_HTML.format(err="<p class=err>Неверный логин или пароль</p>"), status_code=401)
    token = authmod.create_session(user["id"], user)
    resp = RedirectResponse("/app/", status_code=303)
    resp.set_cookie("osint_session", token, httponly=True, samesite="lax",
                    secure=bool(os.getenv("VERCEL")))
    return resp


@app.get("/api/auth/me")
def auth_me(request: Request):
    u = _current_user(request)
    return {"user": u, "auth_enabled": _auth_enabled()}


@app.post("/api/auth/logout")
def auth_logout(request: Request):
    authmod.delete_session(request.cookies.get("osint_session", ""))
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("osint_session")
    return resp


class UserCreateReq(BaseModel):
    username: str
    password: str
    role: str = "analyst"


@app.get("/api/users")
def users_list(request: Request):
    _require_admin(request)
    return authmod.list_users()


@app.post("/api/users")
def users_create(req: UserCreateReq, request: Request):
    _require_admin(request)
    try:
        return authmod.create_user(req.username, req.password, req.role)
    except ValueError as e:
        raise HTTPException(400, str(e))


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


class EnrichReportReq(EnrichReq):
    format: str = "md"  # md | docx | html


@app.post("/api/enrich/report")
def api_enrich_report(req: EnrichReportReq):
    """Аналитический бриф: граф → resolve → analyze → timeline → отчёт (MD/DOCX/PDF)."""
    if req.type not in ENTITY_TYPES:
        raise HTTPException(400, f"Неизвестный тип: {req.type}")
    graph = OG.resolve_entities(enrich_run(req.type, req.value.strip(), req.country))
    md_text = OG.brief_markdown(graph, OG.analyze(graph), OG.timeline(graph))
    safe = re.sub(r"[^\w.-]+", "_", f"{req.type}-{req.value.strip()}")[:60]
    return _report_response(md_text, req.format, f"brief-{safe}")


class ReconReq(BaseModel):
    basis: str = ""
    name: str | None = None
    email: str = ""
    username: str = ""
    github: str = ""
    phone: str = ""
    domain: str = ""
    hops: int = 2
    format: str = "md"


def _recon_build(req: ReconReq) -> dict:
    if not req.basis.strip():
        raise HTTPException(400, "Укажите правовое основание (basis) — это обязательно.")
    if not any([req.name, req.email, req.username, req.github, req.phone, req.domain]):
        raise HTTPException(400, "Нужен хотя бы один сид (name/email/username/github/phone/domain).")

    def split(s):
        return [x.strip() for x in (s or "").split(",") if x.strip()]

    seeds = {
        "_name": (req.name or "").strip() or None,
        "email": split(req.email),
        "username": list(dict.fromkeys(split(req.username) + split(req.github))),
        "phone": split(req.phone),
        "domain": split(req.domain),
    }
    d = recon_build(seeds, max(1, min(req.hops, 3)))
    d["analysis"] = OG.analyze(d)
    d["timeline"] = OG.timeline(d)
    return d


@app.post("/api/recon")
def api_recon(req: ReconReq):
    """Многошаговая разведка личности + корреляция. Гейт правового основания — в коде."""
    return _recon_build(req)


@app.post("/api/recon/report")
def api_recon_report(req: ReconReq):
    d = _recon_build(req)
    safe = re.sub(r"[^\w.-]+", "_", (req.name or "person"))[:50]
    return _report_response(recon_markdown(d), req.format, f"recon-{safe}")


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


# Статус API-ключей (значения НЕ раскрываются — только задан/нет).
_KEY_INFO = [
    ("VIRUSTOTAL_API_KEY", "IOC: репутация IP/домена/URL (VirusTotal)", "free", "https://www.virustotal.com/gui/my-apikey"),
    ("ABUSEIPDB_API_KEY", "IOC: репутация IP (AbuseIPDB)", "free", "https://www.abuseipdb.com/account/api"),
    ("SECURITYTRAILS_API_KEY", "История домена, поддомены, DNS", "free", "https://securitytrails.com/app/account/credentials"),
    ("URLSCAN_API_KEY", "Сканы страниц (urlscan.io)", "free", "https://urlscan.io/user/profile/"),
    ("OPENSANCTIONS_API_KEY", "Санкции/PEP live-поиск", "free", "https://www.opensanctions.org/api/"),
    ("NUMVERIFY_API_KEY", "Телефон: оператор/валидация", "free", "https://numverify.com/product"),
    ("HIBP_API_KEY", "Email в утечках (Have I Been Pwned)", "paid", "https://haveibeenpwned.com/API/Key"),
    ("SHODAN_API_KEY", "Полные данные хоста (сверх InternetDB)", "paid", "https://account.shodan.io/"),
    ("FSSP_API_KEY", "🇷🇺 исполнительные производства", "paid", "https://api-ip.fssp.gov.ru/"),
    ("ODB_API_KEY", "🇺🇦 Opendatabot (карточки компаний)", "paid", "https://opendatabot.com/api"),
    ("YOUCONTROL_API_KEY", "🇺🇦 YouControl (связи/реестры)", "paid", "https://youcontrol.com.ua/"),
]


@app.get("/api/keys")
def api_keys():
    return [{"name": n, "set": bool(os.getenv(n, "").strip()), "desc": d, "tier": t, "url": u}
            for n, d, t, u in _KEY_INFO]


@app.get("/api/tools/curated")
def api_tools_curated():
    f = KNOWLEDGE / "curated-tools.json"
    if not f.exists():
        return {"tools": [], "meta": {}}
    data = json.loads(f.read_text(encoding="utf-8"))
    return {"tools": data.get("tools", []), "meta": data.get("_meta", {})}


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


@app.get("/api/scan/stream")
def api_scan_stream(kind: str, value: str):
    """Старт+стрим скана в одном запросе (serverless-совместимо: без общего стейта/потоков).

    Предпочтительный путь для React-клиента и Vercel. SSE: событие на строку `data:`.
    """
    v = value.strip()
    if not v:
        raise HTTPException(400, "Пустое значение")

    def gen():
        for ev in jobq.run_inline(kind, v):
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


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


class PersonReportReq(PersonReq):
    format: str = "md"


@app.post("/api/person/report")
def api_person_report(req: PersonReportReq):
    if not req.name.strip():
        raise HTTPException(400, "Пустое ФИО")
    d = search_person(req.name.strip(), req.dob, req.rnokpp, req.email or None,
                      req.phone or None, req.username or None, tuple(req.countries))
    safe = re.sub(r"[^\w.-]+", "_", req.name.strip())[:50]
    return _report_response(dossier_to_markdown(d), req.format, f"dossier-{safe}")


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
    return cstore.list_cases(CASES)


class CaseCreateReq(BaseModel):
    slug: str
    title: str = ""
    basis: str = ""


@app.post("/api/cases")
def api_case_create(req: CaseCreateReq):
    try:
        return cstore.create_case(CASES, CASES / "_TEMPLATE", req.slug, req.title, req.basis)
    except (ValueError, FileExistsError) as e:
        raise HTTPException(400, str(e))


class CaseSaveReq(BaseModel):
    result: dict


@app.post("/api/cases/{slug}/save")
def api_case_save(slug: str, req: CaseSaveReq):
    try:
        return cstore.save_result(CASES, slug, req.result)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.get("/api/cases/{slug}")
def api_case_detail(slug: str):
    try:
        return cstore.aggregate(CASES, slug)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/cases/{slug}/report")
def api_case_report(slug: str):
    try:
        return JSONResponse({"markdown": cstore.report_markdown(CASES, slug)})
    except ValueError as e:
        raise HTTPException(400, str(e))


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

    uvicorn.run(app, host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8000")))
