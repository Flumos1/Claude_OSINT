#!/usr/bin/env python3
r"""
analyze.py — аналитический слой поверх графа: разрешение сущностей + анализ + таймлайн + бриф.

Вход — граф JSON, собранный enrich.py/person_recon.py (--json), ИЛИ собери на лету
из сущности. Выход — консольный анализ, JSON и Markdown-бриф (→ osint-report для DOCX/PDF).

    # из готового графа
    python analyze.py --graph ..\cases\<slug>\data\graph.json --report brief.md
    # собрать граф на лету и сразу проанализировать
    python analyze.py --enrich company 14360570
    python analyze.py --enrich domain example.com --json g.json --report brief.md
"""
import argparse
import json
import sys

import osint_graph as G


def _load_or_build(args) -> dict:
    if args.graph:
        with open(args.graph, encoding="utf-8") as f:
            return json.load(f)
    if args.enrich:
        from enrich import run as enrich_run
        etype, value = args.enrich[0], args.enrich[1]
        return enrich_run(etype, value, args.country)
    sys.exit("Укажи --graph FILE или --enrich <type> <value>")


def main():
    ap = argparse.ArgumentParser(description="Анализ OSINT-графа (resolve + analyze + timeline)")
    ap.add_argument("--graph", metavar="FILE", help="готовый граф JSON (от enrich/recon)")
    ap.add_argument("--enrich", nargs=2, metavar=("TYPE", "VALUE"), help="собрать граф на лету")
    ap.add_argument("-c", "--country", default="ua")
    ap.add_argument("--no-resolve", action="store_true", help="не сливать дубли сущностей")
    ap.add_argument("--json", metavar="FILE", help="сохранить {graph,analysis,timeline} в JSON")
    ap.add_argument("--report", metavar="FILE.md", help="сохранить аналитический бриф")
    args = ap.parse_args()

    graph = _load_or_build(args)
    if not args.no_resolve:
        graph = G.resolve_entities(graph)
    an = G.analyze(graph)
    tl = G.timeline(graph)

    s = an["summary"]
    print(f"\n=== АНАЛИЗ ГРАФА ===")
    if graph.get("resolution"):
        print(f"Разрешение сущностей: слито {graph['resolution']['merged']}, "
              f"кластеров {graph['resolution']['clusters']}")
    print(f"Итоговый риск: {s['risk_level']}  | узлов {s['nodes']} · связей {s['edges']} · "
          f"компонент {s['components']}")

    if an["risks"]:
        print("\n[⚠️ Риск-флаги]")
        for r in an["risks"]:
            print(f"  {r['level']:6} {r['label']}: {r['evidence'][:90]}")
    if an["insights"]:
        print("\n[🧠 Выводы/гипотезы]")
        for i in an["insights"]:
            print(f"  ({i['label']}) {i['text']}")
    if an["central"]:
        print("\n[🕸️ Центральные узлы]")
        for c in an["central"][:6]:
            print(f"  {c['type']} «{c['value']}» — связей {c['degree']}")
    if tl["events"]:
        print(f"\n[🗓️ Таймлайн: {len(tl['events'])} событий]")
        for e in tl["events"][:8]:
            print(f"  {e['date']}  {e['what'][:80]}")
        for a in tl["anomalies"]:
            print(f"  ⚑ аномалия: {a}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"graph": graph, "analysis": an, "timeline": tl}, f,
                      ensure_ascii=False, indent=2)
        print(f"\nАнализ (JSON) сохранён: {args.json}")
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(G.brief_markdown(graph, an, tl))
        print(f"Бриф (Markdown) сохранён: {args.report}")


if __name__ == "__main__":
    main()
