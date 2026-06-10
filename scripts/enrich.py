#!/usr/bin/env python3
r"""
enrich.py — раннер энричеров. Принимает сущность (тип + значение), запускает все
подходящие энричеры и собирает единый граф (узлы/связи/факты) с provenance.

Архитектура по мотивам flowsint (см. knowledge/flowsint-integration.md). Граф-вывод
(nodes/edges) совместим с граф-моделью — позже импортируется во flowsint/Neo4j.

Использование:
    python enrich.py --list
    python enrich.py domain example.com
    python enrich.py ip 8.8.8.8
    python enrich.py email someone@example.com
    python enrich.py company 14360570              # ЄДРПОУ (UA, по умолчанию --country ua)
    python enrich.py company 7707083893 -c ru      # ИНН (Россия)
    python enrich.py domain example.com --json ..\cases\<slug>\data\graph.json
"""
import argparse
import json
import sys

from enrichers import ENTITY_TYPES, enrichers_for
from enrichers.base import REGISTRY


def run(entity_type: str, value: str, country: str | None = None) -> dict:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    findings: list[dict] = []
    ran: list[str] = []

    for name, fn in enrichers_for(entity_type, country):
        ran.append(name)
        res = fn(value)
        for n in res.nodes:
            key = n.id
            if key in nodes:
                nodes[key]["attrs"].update({k: v for k, v in n.attrs.items() if v})
            else:
                nodes[key] = {"id": key, "type": n.type, "value": n.value, "attrs": n.attrs}
        for e in res.edges:
            edges.append({"source": e.source, "target": e.target, "rel": e.rel})
        for f in res.findings:
            findings.append({"label": f.label, "text": f.text,
                             "source": f.source, "confidence": f.confidence})
        if res.error:
            findings.append({"label": "ERROR", "text": res.error,
                             "source": name, "confidence": ""})

    # дедуп рёбер
    uniq = {(e["source"], e["target"], e["rel"]): e for e in edges}
    return {
        "input": {"type": entity_type, "value": value, "country": country},
        "enrichers_run": ran,
        "nodes": list(nodes.values()),
        "edges": list(uniq.values()),
        "findings": findings,
    }


def print_summary(graph: dict) -> None:
    inp = graph["input"]
    ctry = f" [{inp.get('country')}]" if inp.get("country") else ""
    print(f"\n=== {inp['type']}: {inp['value']}{ctry} ===")
    print(f"Энричеры: {', '.join(graph['enrichers_run']) or '— нет для этого типа/страны'}")
    print(f"Узлов: {len(graph['nodes'])}  Связей: {len(graph['edges'])}  Фактов: {len(graph['findings'])}")
    print("\n[Факты]")
    for f in graph["findings"]:
        c = f" [{f['confidence']}]" if f["confidence"] else ""
        print(f"  ({f['label']}{c}) {f['text']}  — {f['source']}")
    print("\n[Узлы]")
    for n in graph["nodes"]:
        extra = " ".join(f"{k}={v}" for k, v in n["attrs"].items() if v)
        print(f"  {n['type']}: {n['value']}" + (f"  | {extra}" if extra else ""))
    print("\n[Связи]")
    for e in graph["edges"]:
        print(f"  {e['source']}  --{e['rel']}-->  {e['target']}")


def main():
    ap = argparse.ArgumentParser(description="Раннер OSINT-энричеров (граф)")
    ap.add_argument("type", nargs="?", help=f"тип сущности: {', '.join(sorted(ENTITY_TYPES))}")
    ap.add_argument("value", nargs="?", help="значение сущности")
    ap.add_argument("-c", "--country", default="ua",
                    help="страна для страновых энричеров (ua/ru/...); по умолчанию ua")
    ap.add_argument("--json", metavar="FILE", help="сохранить граф в JSON")
    ap.add_argument("--list", action="store_true", help="показать зарегистрированные энричеры")
    args = ap.parse_args()

    if args.list:
        print("Зарегистрированные энричеры (тип → энричер [страна]):")
        for t in sorted(REGISTRY):
            items = ", ".join(f"{n}[{c or 'any'}]" for n, _, c in REGISTRY[t])
            print(f"  {t}: {items}")
        return

    if not args.type or not args.value:
        ap.error("укажи тип и значение, либо --list")
    if args.type not in ENTITY_TYPES:
        ap.error(f"неизвестный тип. Доступно: {', '.join(sorted(ENTITY_TYPES))}")

    graph = run(args.type, args.value, args.country)
    print_summary(graph)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(graph, f, ensure_ascii=False, indent=2)
        print(f"\nГраф сохранён: {args.json}")


if __name__ == "__main__":
    main()
