#!/usr/bin/env python3
r"""
person_recon.py — многошаговый движок разведки личности по ОТКРЫТЫМ источникам.

Прорыв над person_search.py (одношаговый): здесь идёт ИТЕРАТИВНЫЙ пивотинг —
из каждого найденного идентификатора извлекаются новые (email→gravatar→домен,
ник→github→commit-email/сайт/twitter→новый ник…) и подаются обратно во фронтир,
пока не исчерпаются или не упрётся в лимит шагов. Поверх графа работает ДВИЖОК
КОРРЕЛЯЦИИ: кластеризует сигналы и оценивает достоверность связи с корневой личностью
(CONFIRMED / PROBABLE / POSSIBLE), потому что «совпадение ника/имени ≠ тот же человек».

⚖️ ГЕЙТ ОСНОВАНИЯ (жёстко, в коде): без --basis «…» живое расширение НЕ запускается.
Только открытые/законные источники. Не «пробив», не слитые базы, не обход авторизации.
Поиск частного лица — только при правовом основании (KYC/DD/расследование/взыскание).

CLI:
    python person_recon.py --basis "KYC контрагента" --name "Іван Іваненко" \
        --email a@b.com --username ivanko --github ivanko --hops 2 \
        --json ..\cases\<slug>\data\recon.json --report ..\cases\<slug>\report.md
"""
import argparse
import json
import sys
from datetime import datetime, timezone

from enrichers import enrichers_for
from dorks import person_dorks
from translit import name_variants

BASIS = ("⚖️ Разведка личности допустима ТОЛЬКО при правовом основании "
         "(KYC/DD/расследование/взыскание) и по открытым источникам. Зафиксируй основание.")

# Какие энричеры гоняем в режиме recon (быстро и по теме). Домены НЕ разворачиваем
# тяжёлым domain_recon/typosquat — фиксируем узел и оставляем скилу domain-infra.
RECON_ENRICHERS = {
    "username": {"username_sweep", "github_user"},
    "email": {"email_gravatar", "email_leaks"},
    "phone": {"phone_info"},
}
MAX_RUNS = 30  # предохранитель от разрастания

# Отношения, дающие СИЛЬНУЮ связь идентификатора с корневой личностью.
STRONG_RELS = {"commit_email", "has_email", "links_to", "identity_claim", "reverse_dns"}
MEDIUM_RELS = {"same_handle_claim", "resolves_to"}
# profile_on (username_sweep) — слабое: soft-404 + переиспользование ников.


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


class Graph:
    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = []
        self.findings: list[dict] = []
        self._edgeset: set[tuple] = set()

    def add_node(self, type_, value, hop, via, parent, **attrs) -> str:
        key = f"{type_}:{value.strip().lower()}"
        if key not in self.nodes:
            self.nodes[key] = {"id": key, "type": type_, "value": value, "attrs": dict(attrs),
                               "hop": hop, "via": via, "parent": parent}
        else:
            n = self.nodes[key]
            n["attrs"].update({k: v for k, v in attrs.items() if v})
            if hop < n["hop"]:  # запомним кратчайший путь и сильнейшее отношение
                n["hop"], n["via"], n["parent"] = hop, via, parent
        return key

    def add_edge(self, s, t, rel):
        k = (s, t, rel)
        if k not in self._edgeset:
            self._edgeset.add(k)
            self.edges.append({"source": s, "target": t, "rel": rel})

    def rels_into(self, node_id) -> set[str]:
        return {e["rel"] for e in self.edges if e["target"] == node_id}


def expand(seeds: dict, hops: int) -> Graph:
    """BFS-пивотинг по фронтиру идентификаторов. seeds: {type: [values]}."""
    g = Graph()
    root_name = seeds.get("_name")
    root_id = g.add_node("person", root_name or "(невідомо)", 0, "seed", None)

    frontier: list[tuple[str, str, int, str]] = []  # (type, value, hop, parent_id)
    for typ in ("email", "username", "phone", "domain"):
        for val in seeds.get(typ, []):
            nid = g.add_node(typ, val, 0, "seed", root_id, seed=True)
            g.add_edge(root_id, nid, f"has_{typ}")
            frontier.append((typ, val, 0, nid))

    visited: set[tuple] = set()
    runs = 0
    while frontier and runs < MAX_RUNS:
        typ, val, hop, parent_id = frontier.pop(0)
        if (typ, val.lower()) in visited or hop > hops:
            continue
        visited.add((typ, val.lower()))
        allow = RECON_ENRICHERS.get(typ, set())
        for name, fn in enrichers_for(typ):
            if name not in allow:
                continue
            runs += 1
            res = fn(val)
            for n in res.nodes:
                if n.type == typ and n.value.strip().lower() == val.strip().lower():
                    continue  # это сам входной узел
                via = _pick_rel(res, n)
                nid = g.add_node(n.type, n.value, hop + 1, via, parent_id, **n.attrs)
                # пивотим дальше только «чистые» идентификаторы
                if n.type in ("email", "username", "phone") and (n.type, n.value.lower()) not in visited:
                    frontier.append((n.type, n.value, hop + 1, nid))
                elif n.type == "domain":
                    pass  # фиксируем, но не разворачиваем (→ domain-infra)
            for e in res.edges:
                g.add_edge(e.source, e.target, e.rel)
            for f in res.findings:
                g.findings.append({"label": f.label, "text": f"[{typ}:{val}] {f.text}",
                                   "source": f.source, "confidence": f.confidence})
            if res.error:
                g.findings.append({"label": "ERROR", "text": f"[{name}] {res.error}",
                                   "source": name, "confidence": ""})
    return g


def _pick_rel(res, node) -> str:
    """Определить, каким отношением узел связан с источником (для оценки достоверности)."""
    nid = node.id
    for e in res.edges:
        if e.target == nid:
            return e.rel
    for e in res.edges:
        if e.source == nid:
            return e.rel
    return "mentioned"


def correlate(g: Graph, seed_name: str | None) -> list[dict]:
    """Оценка достоверности связи каждого нетривиального узла с корневой личностью.

    Правила прозрачны (не «чёрный ящик»):
      CONFIRMED — сид оператора ИЛИ взаимная перекрёстная связь (напр. email и в
                  профиле, и в коммитах) ИЛИ совпадение имени с сидом.
      PROBABLE  — один шаг от сильного сида по сильному отношению.
      POSSIBLE  — слабый сигнал: profile_on (soft-404/реюз ников), одно имя, дальний хоп.
    """
    ledger = []
    name_norm = _norm_name(seed_name) if seed_name else None
    for key, n in g.nodes.items():
        if n["type"] == "person" and n["hop"] == 0:
            continue
        rels = g.rels_into(key)
        tier, reason = _classify(n, rels, name_norm)
        ledger.append({"id": key, "type": n["type"], "value": n["value"],
                       "hop": n["hop"], "tier": tier, "reason": reason,
                       "rels": sorted(rels)})
    order = {"CONFIRMED": 0, "PROBABLE": 1, "POSSIBLE": 2}
    ledger.sort(key=lambda x: (order[x["tier"]], x["hop"], x["type"]))
    return ledger


def _classify(n, rels, name_norm):
    if n["attrs"].get("seed") or n["hop"] == 0:
        return "CONFIRMED", "надано оператором (сид)"
    # взаимная перекрёстная связь по нескольким сильным отношениям
    strong = rels & STRONG_RELS
    if len(strong) >= 2:
        return "CONFIRMED", f"взаємне підтвердження: {', '.join(sorted(strong))}"
    if n["type"] == "email" and {"commit_email", "has_email"} <= rels:
        return "CONFIRMED", "email і в профілі, і в комітах"
    # совпадение имени с сидом
    if n["type"] == "person" and name_norm and _norm_name(n["value"]) == name_norm:
        return "CONFIRMED", "ім'я збігається з сидом"
    if strong and n["hop"] <= 1:
        return "PROBABLE", f"1 крок від сида, сильне відношення ({', '.join(sorted(strong))})"
    if n["type"] == "person" and name_norm and _name_overlap(n["value"], name_norm):
        return "PROBABLE", "часткове співпадіння імені з сидом"
    if rels & MEDIUM_RELS:
        return "PROBABLE", f"середнє відношення ({', '.join(sorted(rels & MEDIUM_RELS))})"
    if "profile_on" in rels:
        return "POSSIBLE", "профіль за ніком (можливий soft-404 / чужий нік — підтвердь вручну)"
    return "POSSIBLE", f"слабкий сигнал, хоп {n['hop']}"


def _norm_name(s: str) -> str:
    return " ".join(sorted(w for w in "".join(
        c.lower() if c.isalnum() or c.isspace() else " " for c in s).split()))


def _name_overlap(a: str, name_norm: str) -> bool:
    wa = set(_norm_name(a).split())
    wb = set(name_norm.split())
    return len(wa & wb) >= 2  # ≥2 общих токена (имя+фамилия)


def build(seeds: dict, hops: int) -> dict:
    g = expand(seeds, hops)
    ledger = correlate(g, seeds.get("_name"))
    # дорки по имени — ручной добор (резюме/соцсети/контакты)
    dorks = person_dorks(seeds["_name"]) if seeds.get("_name") else []
    return {
        "collected_at": _now(),
        "seeds": {k: v for k, v in seeds.items() if not k.startswith("_")} | (
            {"name": seeds["_name"]} if seeds.get("_name") else {}),
        "name_variants": name_variants(seeds["_name"]) if seeds.get("_name") else [],
        "nodes": list(g.nodes.values()),
        "edges": g.edges,
        "findings": g.findings,
        "ledger": ledger,
        "dorks": dorks,
    }


def render(d: dict) -> str:
    tiers = {"CONFIRMED": [], "PROBABLE": [], "POSSIBLE": []}
    for e in d["ledger"]:
        tiers[e["tier"]].append(e)
    out = ["", "=" * 70, "РАЗВЕДКА ЛИЧНОСТИ — коррелированный граф", "=" * 70,
           f"Сиды: {d['seeds']}", f"Собрано: {d['collected_at']}",
           f"Узлов: {len(d['nodes'])}  Связей: {len(d['edges'])}  Фактов: {len(d['findings'])}"]
    emoji = {"CONFIRMED": "🟢", "PROBABLE": "🟡", "POSSIBLE": "⚪"}
    for tier in ("CONFIRMED", "PROBABLE", "POSSIBLE"):
        rows = tiers[tier]
        out.append(f"\n{emoji[tier]} {tier} ({len(rows)}) — достоверность связи с объектом")
        if not rows:
            out.append("   —")
        for e in rows:
            out.append(f"   [{e['type']}] {e['value']}  (хоп {e['hop']}) — {e['reason']}")
    out.append("\n[Ключевые факты]")
    for f in d["findings"]:
        if f["label"] == "ERROR" or "профіль існує" in f["text"] or f["confidence"] in ("B2", "B3"):
            c = f" [{f['confidence']}]" if f["confidence"] else ""
            out.append(f"   ({f['label']}{c}) {f['text']} — {f['source']}")
    out.append("\n[Дорки для ручного добора]")
    for dk in d["dorks"][:8]:
        out.append(f"   {dk['label']}: {dk['url']}")
    out.append("\n⚠️ Совпадение ника/имени ≠ тот же человек. Ключевые связи подтверждай ≥2 источниками.")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Многошаговая разведка личности (открытые источники)")
    ap.add_argument("--basis", help="правовое основание (обязательно для запуска)")
    ap.add_argument("--name", help="ФИО / ПІБ объекта")
    ap.add_argument("--email", default="", help="email(ы) через запятую")
    ap.add_argument("--username", default="", help="ник(и) через запятую")
    ap.add_argument("--phone", default="", help="телефон(ы) через запятую")
    ap.add_argument("--github", default="", help="github-ник(и) через запятую (алиас username)")
    ap.add_argument("--domain", default="", help="домен(ы) через запятую")
    ap.add_argument("--hops", type=int, default=2, help="глубина пивотинга (по умолч. 2)")
    ap.add_argument("--json", metavar="FILE")
    ap.add_argument("--report", metavar="FILE.md")
    args = ap.parse_args()

    print("\n" + BASIS)
    if not args.basis:
        print("\n⛔ Не указано правовое основание. Запусти с --basis \"...\" "
              "(например: --basis \"KYC контрагента ООО X\").")
        sys.exit(2)
    if not any([args.name, args.email, args.username, args.phone, args.github, args.domain]):
        ap.error("нужен хотя бы один сид: --name/--email/--username/--phone/--github/--domain")

    def split(s):
        return [x.strip() for x in s.split(",") if x.strip()]

    seeds = {
        "_name": args.name,
        "_basis": args.basis,
        "email": split(args.email),
        "username": list(dict.fromkeys(split(args.username) + split(args.github))),
        "phone": split(args.phone),
        "domain": split(args.domain),
    }
    print(f"Основание: {args.basis}\n")

    d = build(seeds, args.hops)
    print(render(d))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        print(f"\nГраф (JSON) сохранён: {args.json}")
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write("# Досье личности (recon)\n\n> " + BASIS + "\n\n```\n" + render(d) + "\n```\n")
        print(f"Отчёт (Markdown) сохранён: {args.report}")


if __name__ == "__main__":
    main()
