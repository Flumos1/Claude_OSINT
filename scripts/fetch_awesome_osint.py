#!/usr/bin/env python3
"""
fetch_awesome_osint.py — тянет каталог инструментов из awesome-osint (GitHub) и
генерирует локальный категоризированный индекс в knowledge/.

Тот же первоисточник, что использует сайт OSINT Brasil / osint-explorer
(репозиторий jivoi/awesome-osint, ~1300+ инструментов в десятках категорий),
но локально, версионируемо и рядом с нашей методологией.

Создаёт:
  knowledge/tools-index.md    — человекочитаемый индекс по категориям
  knowledge/tools-index.json  — структурированные данные (категория → инструменты)

Использование:
    python fetch_awesome_osint.py                 # обновить индекс
    python fetch_awesome_osint.py --search sherlock   # поиск по локальному индексу
    python fetch_awesome_osint.py --search username --field desc

Зависимости: requests. Источник можно переопределить через --url.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    sys.exit("Нужен пакет requests: pip install -r requirements.txt")

RAW_URL = "https://raw.githubusercontent.com/jivoi/awesome-osint/master/README.md"
SOURCE_REPO = "https://github.com/jivoi/awesome-osint"
HERE = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE = os.path.normpath(os.path.join(HERE, "..", "knowledge"))
MD_OUT = os.path.join(KNOWLEDGE, "tools-index.md")
JSON_OUT = os.path.join(KNOWLEDGE, "tools-index.json")

# ## [↑](#anchor) Category   /   ### [↑](#anchor) Subcategory
HEADER_RE = re.compile(r"^(#{2,3})\s+(?:\[[^\]]*\]\([^)]*\)\s*)*(.+?)\s*$")
# * [Name](url) - description   (bullet может быть * или -)
TOOL_RE = re.compile(r"^\s*[*\-]\s+\[(?P<name>[^\]]+)\]\((?P<url>[^)]+)\)\s*(?:[-–—]\s*(?P<desc>.*))?$")

SKIP_HEADERS = {"table of contents", "contents", "license", "contributing", "credits"}


def fetch(url):
    r = requests.get(url, headers={"User-Agent": "osint-tools-index/1.0"}, timeout=30)
    r.raise_for_status()
    return r.text


def parse(md):
    """Возвращает список категорий: {category, subcategory, tools:[{name,url,desc}]}."""
    sections = []
    category = None
    subcategory = None
    in_code = False

    for line in md.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue

        h = HEADER_RE.match(line)
        if h:
            level, title = len(h.group(1)), h.group(2).strip()
            if title.lower() in SKIP_HEADERS:
                category = subcategory = None
                continue
            if level == 2:
                category, subcategory = title, None
            elif level == 3:
                subcategory = title
            continue

        t = TOOL_RE.match(line)
        if t and category:
            sec = _section(sections, category, subcategory)
            sec["tools"].append({
                "name": t.group("name").strip(),
                "url": t.group("url").strip(),
                "desc": (t.group("desc") or "").strip(),
            })
    return [s for s in sections if s["tools"]]


def _section(sections, category, subcategory):
    for s in sections:
        if s["category"] == category and s["subcategory"] == subcategory:
            return s
    s = {"category": category, "subcategory": subcategory, "tools": []}
    sections.append(s)
    return s


def write_outputs(sections, source_url):
    ts = datetime.now(timezone.utc).isoformat()
    total = sum(len(s["tools"]) for s in sections)
    cats = sorted({s["category"] for s in sections})

    data = {"generated_at": ts, "source": source_url, "repo": SOURCE_REPO,
            "total_tools": total, "categories": len(cats), "sections": sections}
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    lines = [
        "# Индекс инструментов (awesome-osint)",
        "",
        f"> Автогенерация из [{SOURCE_REPO}]({SOURCE_REPO}) — НЕ редактировать вручную.",
        f"> Обновить: `python scripts/fetch_awesome_osint.py`. Сгенерировано: {ts}.",
        f"> Всего инструментов: **{total}** в **{len(cats)}** категориях.",
        f"> Это широкий международный каталог; реестры по странам — в [sources/](sources/).",
        ">",
        "> ⚠️ Каталог импортирован «как есть» и содержит инструменты, которые могут выходить",
        "> за наши этические/правовые рамки (сервисы «пробива», скрейперы, серые боты).",
        "> Перед использованием сверяйся с [ethics-legal.md](ethics-legal.md) — наличие в списке ≠ одобрение.",
        "",
        "## Категории",
        "",
    ]
    for c in cats:
        anchor = re.sub(r"[^a-z0-9]+", "-", c.lower()).strip("-")
        lines.append(f"- [{c}](#{anchor})")
    lines.append("")

    last_cat = None
    for s in sections:
        if s["category"] != last_cat:
            lines += ["", f"## {s['category']}", ""]
            last_cat = s["category"]
        if s["subcategory"]:
            lines += [f"### {s['subcategory']}", ""]
        for tool in s["tools"]:
            desc = f" — {tool['desc']}" if tool["desc"] else ""
            lines.append(f"- [{tool['name']}]({tool['url']}){desc}")
        lines.append("")

    with open(MD_OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return total, len(cats)


def search(term, field):
    if not os.path.exists(JSON_OUT):
        sys.exit("Индекс не найден. Сначала запусти без --search для генерации.")
    with open(JSON_OUT, encoding="utf-8") as f:
        data = json.load(f)
    term = term.lower()
    hits = []
    for s in data["sections"]:
        for tool in s["tools"]:
            hay = tool["name"] if field == "name" else \
                  tool["desc"] if field == "desc" else \
                  f"{tool['name']} {tool['desc']} {s['category']} {s.get('subcategory') or ''}"
            if term in hay.lower():
                hits.append((s["category"], tool))
    print(f"Найдено: {len(hits)} (по '{term}', поле={field})\n")
    for cat, tool in hits[:80]:
        print(f"[{cat}] {tool['name']} — {tool['url']}")
        if tool["desc"]:
            print(f"    {tool['desc']}")
    if len(hits) > 80:
        print(f"\n… и ещё {len(hits) - 80}")


def main():
    ap = argparse.ArgumentParser(description="Локальный индекс инструментов из awesome-osint")
    ap.add_argument("--url", default=RAW_URL, help="raw URL README источника")
    ap.add_argument("--search", metavar="TERM", help="искать по локальному индексу")
    ap.add_argument("--field", choices=["name", "desc", "all"], default="all",
                    help="поле поиска (по умолчанию all)")
    args = ap.parse_args()

    if args.search:
        search(args.search, args.field)
        return

    print(f"Загрузка {args.url} …")
    md = fetch(args.url)
    sections = parse(md)
    total, cats = write_outputs(sections, args.url)
    print(f"Готово: {total} инструментов, {cats} категорий")
    print(f"  {MD_OUT}")
    print(f"  {JSON_OUT}")


if __name__ == "__main__":
    main()
