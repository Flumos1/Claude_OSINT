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
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
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


def _report_response(markdown: str, fmt: str, filename: str):
    """Отдать отчёт в нужном формате: md (JSON), docx (файл) или html (JSON для печати→PDF)."""
    fmt = (fmt or "md").lower()
    if fmt == "docx":
        data = markdown_to_docx(markdown)
        return Response(content=data,
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
    """Аналитический бриф по сущности: собрать граф → resolve → analyze → timeline → отчёт."""
    if req.type not in ENTITY_TYPES:
        raise HTTPException(400, f"Неизвестный тип: {req.type}")
    graph = enrich_run(req.type, req.value.strip(), req.country)
    graph = OG.resolve_entities(graph)
    md_text = OG.brief_markdown(graph, OG.analyze(graph), OG.timeline(graph))
    safe = re.sub(r"[^\w.-]+", "_", f"{req.type}-{req.value.strip()}")[:60]
    return _report_response(md_text, req.format, f"brief-{safe}")


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


class ReconReq(BaseModel):
    basis: str = ""
    name: str | None = None
    email: str = ""
    username: str = ""
    github: str = ""
    phone: str = ""
    domain: str = ""
    hops: int = 2


@app.post("/api/recon")
def api_recon(req: ReconReq):
    """Многошаговая разведка личности + анализ. Гейт правового основания — в коде."""
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


class ReconReportReq(ReconReq):
    format: str = "md"


@app.post("/api/recon/report")
def api_recon_report(req: ReconReportReq):
    if not req.basis.strip():
        raise HTTPException(400, "Укажите правовое основание (basis) — это обязательно.")

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
    safe = re.sub(r"[^\w.-]+", "_", (req.name or "person"))[:50]
    return _report_response(recon_markdown(d), req.format, f"recon-{safe}")


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


SLUG_RX = re.compile(r"^[a-z0-9][a-z0-9-]{1,60}$")


def _ensure_case(slug: str) -> Path:
    """Вернуть каталог кейса, создав его из _TEMPLATE при отсутствии."""
    d = CASES / slug
    if not d.exists():
        tpl = CASES / "_TEMPLATE"
        shutil.copytree(tpl, d)
        brief = d / "00-brief.md"
        if brief.exists():
            txt = brief.read_text(encoding="utf-8").replace("{{slug}}", slug).replace(
                "{{ГГГГ-ММ-ДД}}", datetime.now().strftime("%Y-%m-%d"))
            brief.write_text(txt, encoding="utf-8")
    (d / "data").mkdir(exist_ok=True)
    return d


class CaseSaveReq(BaseModel):
    slug: str
    source: str            # enrich | recon | person
    data: dict             # граф/дичье/запрос из состояния фронтенда


@app.post("/api/case/save")
def api_case_save(req: CaseSaveReq):
    slug = req.slug.strip().lower()
    if not SLUG_RX.match(slug):
        raise HTTPException(400, "Слаг: строчные латиница/цифры/дефис, 2–61 символ (напр. acme-dd).")
    if not req.data:
        raise HTTPException(400, "Нет данных для сохранения.")

    # собрать markdown + label по источнику
    if req.source == "enrich":
        g = OG.resolve_entities(req.data)
        markdown = OG.brief_markdown(g, OG.analyze(g), OG.timeline(g))
        inp = req.data.get("input", {})
        label = f"{inp.get('type', 'graph')}-{inp.get('value', '')}"
    elif req.source == "recon":
        d = dict(req.data)
        d.setdefault("analysis", OG.analyze(d))
        d.setdefault("timeline", OG.timeline(d))
        markdown = recon_markdown(d)
        label = "recon-" + ((d.get("seeds") or {}).get("name") or "person")
    elif req.source == "person":
        q = req.data
        dossier = search_person(q.get("name", "").strip(), q.get("dob"), q.get("rnokpp"),
                                q.get("email") or None, q.get("phone") or None,
                                q.get("username") or None, tuple(q.get("countries") or ["ua"]))
        markdown = dossier_to_markdown(dossier)
        req.data["_dossier"] = dossier  # сохраним и полный результат
        label = "person-" + (q.get("name") or "person")
    else:
        raise HTTPException(400, f"Неизвестный источник: {req.source}")

    case = _ensure_case(slug)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe = re.sub(r"[^\w.-]+", "_", label)[:60].strip("_")
    stem = f"{safe}-{ts}"
    (case / "data" / f"{stem}.json").write_text(
        json.dumps(req.data, ensure_ascii=False, indent=2), encoding="utf-8")
    (case / "data" / f"{stem}.md").write_text(markdown, encoding="utf-8")

    # дописать строку в журнал
    logf = case / "log.md"
    if logf.exists():
        row = (f"| {datetime.now().strftime('%Y-%m-%d %H:%M')} | Сохранение из веб-платформы "
               f"({req.source}) | enrich-движок | {label} | data/{stem}.json, data/{stem}.md |\n")
        with logf.open("a", encoding="utf-8") as f:
            f.write(row)

    return {"slug": slug, "saved": [f"data/{stem}.json", f"data/{stem}.md"], "created": case.name}


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
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
