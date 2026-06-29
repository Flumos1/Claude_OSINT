"""
cases_store.py — менеджмент кейсов для веб-платформы.

Человекочитаемая структура кейса (00-brief.md, entities.md, log.md) остаётся как есть
в cases/<slug>/. Машиночитаемые собранные результаты складываются в
cases/<slug>/data/collected.json (data/ в .gitignore — чувствительно).

aggregate() сливает все сохранённые результаты в единый граф (узлы по id) — основа
для сквозного графа кейса и отчёта.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_slug(slug: str) -> str:
    s = slug.strip().lower().replace(" ", "-")
    s = re.sub(r"[^a-z0-9-]", "", s)
    if not SLUG_RE.match(s):
        raise ValueError("Недопустимый slug (a-z, 0-9, дефис; 2–49 символов)")
    return s


def create_case(cases_dir: Path, template_dir: Path, slug: str, title: str = "",
                basis: str = "") -> dict:
    slug = safe_slug(slug)
    cdir = cases_dir / slug
    if cdir.exists():
        raise FileExistsError(f"Кейс '{slug}' уже существует")
    cdir.mkdir(parents=True)
    # бриф из шаблона с подстановкой
    brief_tpl = (template_dir / "00-brief.md")
    text = brief_tpl.read_text(encoding="utf-8") if brief_tpl.exists() else "# Бриф кейса: {{slug}}\n"
    text = text.replace("{{slug}}", slug)
    text = text.replace("{{что/кто проверяется}}", title or "")
    text = text.replace("{{KYC / контрагент / расследование / согласие / ...}}", basis or "")
    text = text.replace("{{ГГГГ-ММ-ДД}}", _now()[:10])
    (cdir / "00-brief.md").write_text(text, encoding="utf-8")
    for f in ("entities.md", "log.md"):
        src = template_dir / f
        if src.exists():
            (cdir / f).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return {"slug": slug, "title": title}


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
    cdir = cases_dir / slug
    if not cdir.exists():
        raise FileNotFoundError(f"Кейс '{slug}' не найден")
    data = _read_collected(cases_dir, slug)
    entry = {
        "at": _now(),
        "query": result.get("input", {}),
        "nodes": result.get("nodes", []),
        "edges": result.get("edges", []),
        "findings": result.get("findings", []),
    }
    data["saves"].append(entry)
    p = _collected_path(cases_dir, slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"slug": slug, "saves": len(data["saves"])}


def aggregate(cases_dir: Path, slug: str) -> dict:
    data = _read_collected(cases_dir, slug)
    nodes: dict[str, dict] = {}
    edges: dict[tuple, dict] = {}
    findings: list[dict] = []
    for s in data["saves"]:
        for n in s["nodes"]:
            key = n["id"]
            if key in nodes:
                nodes[key]["attrs"].update({k: v for k, v in n.get("attrs", {}).items() if v})
            else:
                nodes[key] = {"id": key, "type": n["type"], "value": n["value"], "attrs": dict(n.get("attrs", {}))}
        for e in s["edges"]:
            edges[(e["source"], e["target"], e["rel"])] = e
        for f in s["findings"]:
            findings.append({**f, "_query": s["query"]})
    return {
        "slug": slug,
        "saves": len(data["saves"]),
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "findings": findings,
    }


def report_markdown(cases_dir: Path, slug: str) -> str:
    slug = safe_slug(slug)
    cdir = cases_dir / slug
    agg = aggregate(cases_dir, slug)
    brief = (cdir / "00-brief.md")
    L = [f"# Отчёт по кейсу: {slug}", "", f"_Сгенерировано: {_now()}_", ""]
    if brief.exists():
        L += ["## Бриф", "", brief.read_text(encoding="utf-8").strip(), ""]
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
    out = []
    for d in sorted(cases_dir.glob("*")):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        brief = ""
        bf = d / "00-brief.md"
        if bf.exists():
            brief = bf.read_text(encoding="utf-8")[:300]
        saves = len(_read_collected(cases_dir, d.name).get("saves", []))
        out.append({"slug": d.name, "brief": brief, "saves": saves})
    return out
