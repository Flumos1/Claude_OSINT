#!/usr/bin/env python3
r"""
graphlib.py — слой над графом OSINT: разрешение сущностей + аналитика + таймлайн.

Работает с единым форматом графа, который отдают enrich.run / person_recon.build:
    {"nodes":[{id,type,value,attrs,...}], "edges":[{source,target,rel}], "findings":[...]}

Три функции:
  • resolve_entities(graph)  — слить дубли сущностей (напр. одного человека, найденного
    через ЄДР/github/НАЗК) в один узел; переписать рёбра; пометить merged_from.
  • analyze(graph)           — детерминированный анализ: центральность, кластеры, риск-флаги,
    выводы/гипотезы (маркированные), — основа для нарратива и osint-report.
  • timeline(graph)          — хронология из всех дат + флаги аномалий.

Всё прозрачно (правила, а не «чёрный ящик»): факт остаётся фактом с источником, вывод и
гипотеза помечаются явно (label INFERENCE/HYPOTHESIS) — золотое правило факт/вывод/гипотеза.
"""
from __future__ import annotations

import re
from collections import defaultdict

# ── Разрешение сущностей ──────────────────────────────────────────────────────

# Отношения «это одна и та же сущность / прямое владение» — кандидаты на слияние личности.
IDENTITY_RELS = {"identity_claim", "same_handle_claim"}


def _norm_name(s: str) -> str:
    toks = "".join(c.lower() if c.isalnum() or c.isspace() else " " for c in s).split()
    return " ".join(sorted(toks))


def resolve_entities(graph: dict) -> dict:
    """Слить дублирующиеся сущности. Возвращает НОВЫЙ граф с merged-узлами."""
    nodes = {n["id"]: dict(n) for n in graph["nodes"]}
    parent: dict[str, str] = {nid: nid for nid in nodes}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra  # a — «канонический» (обычно раньше добавлен / меньше хоп)

    # 1) люди с эквивалентным нормализованным именем → одна сущность
    persons = [n for n in nodes.values() if n["type"] == "person"]
    by_name: dict[str, list[str]] = defaultdict(list)
    for p in persons:
        by_name[_norm_name(p["value"])].append(p["id"])
    for ids in by_name.values():
        for other in ids[1:]:
            union(ids[0], other)

    # 2) узлы, соединённые «identity»-отношением, если совместимы по типу/имени
    for e in graph["edges"]:
        if e["rel"] in IDENTITY_RELS and e["source"] in nodes and e["target"] in nodes:
            s, t = nodes[e["source"]], nodes[e["target"]]
            if s["type"] == "person" and t["type"] == "person":
                union(e["source"], e["target"])

    # построить канонические узлы
    canon: dict[str, dict] = {}
    merged_from: dict[str, list[str]] = defaultdict(list)
    for nid, n in nodes.items():
        root = find(nid)
        if root not in canon:
            canon[root] = dict(nodes[root]); canon[root]["attrs"] = dict(nodes[root].get("attrs", {}))
        if nid != root:
            merged_from[root].append(nid)
            for k, v in n.get("attrs", {}).items():
                canon[root]["attrs"].setdefault(k, v)
    for root, srcs in merged_from.items():
        canon[root]["attrs"]["merged_from"] = sorted(set(srcs))

    # переписать рёбра на канонические id, выкинуть петли/дубли
    seen = set(); edges = []
    for e in graph["edges"]:
        s, t = find(e.get("source", "")), find(e.get("target", ""))
        if not s or not t or s == t:
            continue
        key = (s, t, e["rel"])
        if key not in seen:
            seen.add(key); edges.append({"source": s, "target": t, "rel": e["rel"]})

    out = dict(graph)
    out["nodes"] = list(canon.values())
    out["edges"] = edges
    out["resolution"] = {"merged": sum(len(v) for v in merged_from.values()),
                         "clusters": len(canon)}
    return out


# ── Аналитика ─────────────────────────────────────────────────────────────────

RISK_RULES = [
    (re.compile(r"санкц|sanction|ofac|sdn", re.I), "HIGH", "Санкции/PEP-риск"),
    (re.compile(r"утеч|leak|breach|pwn|скомпром|знайдено в.*витік", re.I), "MEDIUM", "Компрометация в утечках"),
    (re.compile(r"знайдено секрет|leaked secret|викрит.*секрет|expos\w+ (key|token|secret)", re.I), "HIGH", "Утёкшие секреты"),
    (re.compile(r"судов.*справ|court case|позов|виконавч.*провадж|штраф.*грн|penalt", re.I), "MEDIUM", "Судебные/долговые риски"),
    (re.compile(r"зареєстрован.*(схож|typosquat)|тайпсквот.*зарег", re.I), "MEDIUM", "Тайпсквоттинг бренда"),
    (re.compile(r"банкрот|bankrupt|ліквідац|liquidat", re.I), "MEDIUM", "Банкротство/ликвидация"),
    (re.compile(r"у розшуку|wanted person|в розыске", re.I), "HIGH", "Розыск"),
    # threat-intel: вредоносный индикатор (ioc_reputation) — malicious/high-confidence
    (re.compile(r"malicious=[1-9]|класифікація=malicious|classification=malicious|confidence=(?:[5-9]\d|100)%", re.I),
     "HIGH", "Вредоносный индикатор (threat-intel)"),
    # открытая поверхность атаки: CVE на сервисах IP (ip_ports)
    (re.compile(r"уразлив\w*\s*cve|\bCVE-\d{4}-\d{3,}", re.I), "MEDIUM", "Открытые уязвимости (CVE)"),
]

# Источники-указатели/инструкции (не наблюдения) — исключаются из риск-детекции.
_SKIP_RISK_SRC = {"deep-link", "deep-link реєстру", "config", "dorks", "tools-catalog",
                  "методология", "company-dd", "ethics-legal", "translit", "username_sweep"}


def _substantive(f: dict) -> bool:
    """Факт-наблюдение, а не ссылка/инструкция/мета (риски считаем только по таким)."""
    if f.get("label") != "FACT":
        return False
    if f.get("source", "") in _SKIP_RISK_SRC:
        return False
    if "http://" in f.get("text", "") or "https://" in f.get("text", ""):
        return False  # указатель на реестр, а не факт
    return True


def _degree(graph: dict) -> dict[str, int]:
    deg: dict[str, int] = defaultdict(int)
    for e in graph["edges"]:
        deg[e["source"]] += 1
        deg[e["target"]] += 1
    return deg


def _components(graph: dict) -> list[list[str]]:
    adj: dict[str, set] = defaultdict(set)
    ids = {n["id"] for n in graph["nodes"]}
    for e in graph["edges"]:
        if e["source"] in ids and e["target"] in ids:
            adj[e["source"]].add(e["target"]); adj[e["target"]].add(e["source"])
    seen = set(); comps = []
    for nid in ids:
        if nid in seen:
            continue
        stack, comp = [nid], []
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x); comp.append(x)
            stack.extend(adj[x] - seen)
        comps.append(sorted(comp))
    return sorted(comps, key=len, reverse=True)


def analyze(graph: dict) -> dict:
    """Детерминированный анализ графа: центральность, кластеры, риски, выводы/гипотезы."""
    nodes = {n["id"]: n for n in graph["nodes"]}
    deg = _degree(graph)
    comps = _components(graph)

    # центральность — топ-коннекторы
    central = sorted(({"id": nid, "type": nodes[nid]["type"], "value": nodes[nid]["value"],
                       "degree": d} for nid, d in deg.items() if nid in nodes),
                     key=lambda x: x["degree"], reverse=True)[:8]

    # риск-флаги — только по содержательным наблюдениям (не по ссылкам/инструкциям)
    risks = []
    for f in graph.get("findings", []):
        if not _substantive(f):
            continue
        for rx, level, label in RISK_RULES:
            if rx.search(f.get("text", "")):
                risks.append({"level": level, "label": label,
                              "evidence": f["text"], "source": f.get("source", "")})
                break

    # выводы/гипотезы (маркированные)
    insights = []
    # общие селекторы, связывающие ≥2 организаций/персон → возможная аффилированность
    shared = _shared_selectors(graph, nodes)
    for sel_id, owners in shared.items():
        if len(owners) >= 2:
            insights.append({"label": "HYPOTHESIS",
                             "text": f"Общий селектор {nodes[sel_id]['type']} «{nodes[sel_id]['value']}» "
                                     f"связывает {len(owners)} сущностей → возможная аффилированность/один контролёр.",
                             "source": "osint_graph.shared_selector",
                             "refs": owners})
    # мост между кластерами
    for c in central:
        if c["degree"] >= 3 and c["type"] in ("person", "email", "phone", "domain"):
            insights.append({"label": "INFERENCE",
                             "text": f"{c['type']} «{c['value']}» — центральный узел (связей: {c['degree']}); "
                                     f"вероятная точка контроля/пивота.",
                             "source": "osint_graph.centrality"})
    # широкая поверхность атаки: у IP много открытых портов (ip_ports)
    for nid, n in nodes.items():
        ports = (n.get("attrs") or {}).get("open_ports")
        if isinstance(ports, str) and ports.count(",") >= 5:
            insights.append({"label": "INFERENCE",
                             "text": f"IP «{n['value']}»: широкая поверхность ({ports.count(',')+1} портов) — "
                                     f"проверь необходимость каждого сервиса.",
                             "source": "osint_graph.attack_surface"})

    risk_level = "HIGH" if any(r["level"] == "HIGH" for r in risks) else (
        "MEDIUM" if risks else "LOW")
    return {
        "summary": {"nodes": len(nodes), "edges": len(graph["edges"]),
                    "components": len(comps), "risk_level": risk_level},
        "central": central,
        "components": [{"size": len(c), "members": c} for c in comps[:5]],
        "risks": risks,
        "insights": insights,
    }


def _shared_selectors(graph, nodes):
    """selector_id -> [owner_ids] для email/phone/domain, к которым цепляется ≥1 сущность."""
    owners = defaultdict(set)
    sel_types = {"email", "phone", "domain"}
    ent_types = {"person", "company"}
    for e in graph["edges"]:
        s, t = e.get("source"), e.get("target")
        if s in nodes and t in nodes:
            if nodes[t]["type"] in sel_types and nodes[s]["type"] in ent_types:
                owners[t].add(s)
            if nodes[s]["type"] in sel_types and nodes[t]["type"] in ent_types:
                owners[s].add(t)
    return {k: sorted(v) for k, v in owners.items()}


# ── Таймлайн ──────────────────────────────────────────────────────────────────

DATE_RX = re.compile(r"\b(19|20)\d{2}(?:-\d{2}(?:-\d{2})?)?\b")


def timeline(graph: dict) -> dict:
    """Хронология из дат в attrs узлов и текстах фактов + флаги аномалий."""
    events = []
    for n in graph["nodes"]:
        for k, v in (n.get("attrs") or {}).items():
            for m in DATE_RX.finditer(str(v)):
                events.append({"date": m.group(0), "what": f"{n['type']} {n['value']}: {k}={v}",
                               "kind": "node"})
    for f in graph.get("findings", []):
        if f.get("label") == "ERROR":
            continue
        for m in DATE_RX.finditer(f.get("text", "")):
            events.append({"date": m.group(0), "what": f["text"][:120],
                           "kind": "finding", "source": f.get("source", "")})
    events.sort(key=lambda e: e["date"])

    anomalies = []
    years = [int(e["date"][:4]) for e in events]
    if years:
        span = max(years) - min(years)
        if span > 40:
            anomalies.append(f"Большой разброс дат ({min(years)}–{max(years)}, {span} лет) — "
                             f"проверь смешение разных сущностей.")
    # свежесозданные объекты (текущий год) рядом с рисковыми фактами
    recent = [e for e in events if e["date"][:4] >= "2025"]
    if recent and any(r for r in analyze(graph)["risks"]):
        anomalies.append(f"Есть недавно созданные объекты ({len(recent)}) при наличии риск-флагов — "
                         f"возможна свежая инфраструктура под активность.")
    return {"events": events, "anomalies": anomalies}


def brief_markdown(graph: dict, an: dict, tl: dict) -> str:
    """Аналитический бриф в Markdown (далее → osint-report для DOCX/PDF)."""
    s = an["summary"]
    L = ["# Аналитический бриф (авто)", "",
         f"**Итоговый риск:** `{s['risk_level']}` · узлов {s['nodes']} · связей {s['edges']} · "
         f"кластеров {s['components']}", ""]
    if an["risks"]:
        L += ["## ⚠️ Риск-флаги", ""]
        for r in an["risks"]:
            L.append(f"- `{r['level']}` **{r['label']}** — {r['evidence']} _(— {r['source']})_")
        L.append("")
    if an["insights"]:
        L += ["## 🧠 Выводы и гипотезы (не факты — проверять)", ""]
        for i in an["insights"]:
            L.append(f"- **{i['label']}** {i['text']}")
        L.append("")
    if an["central"]:
        L += ["## 🕸️ Центральные узлы", ""]
        for c in an["central"]:
            L.append(f"- {c['type']} «{c['value']}» — связей: {c['degree']}")
        L.append("")
    if tl["events"]:
        L += ["## 🗓️ Таймлайн", ""]
        for e in tl["events"][:20]:
            L.append(f"- **{e['date']}** — {e['what']}")
        if tl["anomalies"]:
            L += ["", "**Аномалии:**"] + [f"- {a}" for a in tl["anomalies"]]
        L.append("")
    L += ["---", "> Авто-анализ графа. Факты — со ссылками; выводы/гипотезы требуют ручной "
          "верификации (≥2 источника). Не является юридическим заключением."]
    return "\n".join(L)
