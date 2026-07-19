"""
cases_store.py — менеджмент кейсов. Два бэкенда, единый API:
  • локально/Docker — файлы: человекочитаемая структура cases/<slug>/ (00-brief.md,
    entities.md, log.md) + машиночитаемый data/collected.json;
  • на Vercel (serverless) — Upstash Redis KV: мета кейса + список сохранений в KV
    (файловая система read-only). Выбор автоматический по kv.kv_enabled().

aggregate() сливает все сохранённые результаты в единый граф (узлы по id).
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import kv

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}$")

_C = "osint:case:"       # osint:case:<slug> -> {slug,title,basis,brief,created}
_CSET = "osint:cases"    # set слагов
_SAVES = "osint:case:{}:saves"  # список JSON-сохранений


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_slug(slug: str) -> str:
    s = slug.strip().lower().replace(" ", "-")
    s = re.sub(r"[^a-z0-9-]", "", s)
    if not SLUG_RE.match(s):
        raise ValueError("Недопустимый slug (a-z, 0-9, дефис; 2–49 символов)")
    return s


def _brief_text(template_dir: Path, slug: str, title: str, basis: str) -> str:
    tpl = template_dir / "00-brief.md"
    text = tpl.read_text(encoding="utf-8") if tpl.exists() else "# Бриф кейса: {{slug}}\n"
    text = text.replace("{{slug}}", slug)
    text = text.replace("{{что/кто проверяется}}", title or "")
    text = text.replace("{{KYC / контрагент / расследование / согласие / ...}}", basis or "")
    text = text.replace("{{ГГГГ-ММ-ДД}}", _now()[:10])
    return text


def create_case(cases_dir: Path, template_dir: Path, slug: str, title: str = "",
                basis: str = "") -> dict:
    slug = safe_slug(slug)
    brief = _brief_text(template_dir, slug, title, basis)

    if kv.kv_enabled():
        if kv.exists(_C + slug):
            raise FileExistsError(f"Кейс '{slug}' уже существует")
        kv.set_json(_C + slug, {"slug": slug, "title": title, "basis": basis,
                                "brief": brief, "created": _now()})
        kv.sadd(_CSET, slug)
        return {"slug": slug, "title": title}

    cdir = cases_dir / slug
    if cdir.exists():
        raise FileExistsError(f"Кейс '{slug}' уже существует")
    cdir.mkdir(parents=True)
    (cdir / "00-brief.md").write_text(brief, encoding="utf-8")
    for f in ("entities.md", "log.md"):
        src = template_dir / f
        if src.exists():
            (cdir / f).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return {"slug": slug, "title": title}


def _entry(result: dict) -> dict:
    return {
        "at": _now(),
        "query": result.get("input", {}),
        "nodes": result.get("nodes", []),
        "edges": result.get("edges", []),
        "findings": result.get("findings", []),
    }


def _collected_path(cases_dir: Path, slug: str) -> Path:
    return cases_dir / safe_slug(slug) / "data" / "collected.json"


def _read_collected(cases_dir: Path, slug: str) -> dict:
    p = _collected_path(cases_dir, slug)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"saves": []}


def save_result(cases_dir: Path, slug: str, result: dict) -> dict:
    slug = safe_slug(slug)
    if kv.kv_enabled():
        if not kv.exists(_C + slug):
            raise FileNotFoundError(f"Кейс '{slug}' не найден")
        kv.rpush(_SAVES.format(slug), json.dumps(_entry(result), ensure_ascii=False))
        return {"slug": slug, "saves": kv.llen(_SAVES.format(slug))}

    cdir = cases_dir / slug
    if not cdir.exists():
        raise FileNotFoundError(f"Кейс '{slug}' не найден")
    data = _read_collected(cases_dir, slug)
    data["saves"].append(_entry(result))
    p = _collected_path(cases_dir, slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"slug": slug, "saves": len(data["saves"])}


def _saves(cases_dir: Path, slug: str) -> list[dict]:
    if kv.kv_enabled():
        return [json.loads(s) for s in kv.lrange(_SAVES.format(slug))]
    return _read_collected(cases_dir, slug).get("saves", [])


def aggregate(cases_dir: Path, slug: str) -> dict:
    slug = safe_slug(slug)
    saves = _saves(cases_dir, slug)
    nodes: dict[str, dict] = {}
    edges: dict[tuple, dict] = {}
    findings: list[dict] = []
    for s in saves:
        for n in s.get("nodes", []):
            key = n["id"]
            if key in nodes:
                nodes[key]["attrs"].update({k: v for k, v in n.get("attrs", {}).items() if v})
            else:
                nodes[key] = {"id": key, "type": n["type"], "value": n["value"],
                              "attrs": dict(n.get("attrs", {}))}
        for e in s.get("edges", []):
            edges[(e["source"], e["target"], e["rel"])] = e
        for f in s.get("findings", []):
            findings.append({**f, "_query": s.get("query", {})})
    return {"slug": slug, "saves": len(saves), "nodes": list(nodes.values()),
            "edges": list(edges.values()), "findings": findings}


def _brief_of(cases_dir: Path, slug: str) -> str:
    if kv.kv_enabled():
        meta = kv.get_json(_C + slug) or {}
        return meta.get("brief", "")
    bf = cases_dir / slug / "00-brief.md"
    return bf.read_text(encoding="utf-8").strip() if bf.exists() else ""


def report_markdown(cases_dir: Path, slug: str) -> str:
    slug = safe_slug(slug)
    agg = aggregate(cases_dir, slug)
    L = [f"# Отчёт по кейсу: {slug}", "", f"_Сгенерировано: {_now()}_", ""]
    brief = _brief_of(cases_dir, slug)
    if brief:
        L += ["## Бриф", "", brief.strip(), ""]
    L += ["## Сущности", "", "| Тип | Значение | Атрибуты |", "|---|---|---|"]
    for n in agg["nodes"]:
        attrs = ", ".join(f"{k}={v}" for k, v in n["attrs"].items() if v) or "—"
        L.append(f"| {n['type']} | {n['value']} | {attrs} |")
    L += ["", "## Находки", ""]
    for f in agg["findings"]:
        c = f" `[{f['confidence']}]`" if f.get("confidence") else ""
        L.append(f"- **{f['label']}**{c} {f['text']} — _{f['source']}_")
    L += ["", "---",
          "> Открытые источники на дату сбора. Совпадение идентификаторов не гарантирует "
          "тождество. Не является юридическим заключением."]
    return "\n".join(L)


def list_cases(cases_dir: Path) -> list[dict]:
    if kv.kv_enabled():
        out = []
        for slug in sorted(kv.smembers(_CSET)):
            meta = kv.get_json(_C + slug) or {}
            out.append({"slug": slug, "brief": (meta.get("brief", "") or "")[:300],
                        "saves": kv.llen(_SAVES.format(slug))})
        return out
    out = []
    for d in sorted(cases_dir.glob("*")):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        bf = d / "00-brief.md"
        brief = bf.read_text(encoding="utf-8")[:300] if bf.exists() else ""
        out.append({"slug": d.name, "brief": brief,
                    "saves": len(_read_collected(cases_dir, d.name).get("saves", []))})
    return out
