#!/usr/bin/env python3
"""
fetch_wmn.py — тянет датасет WhatsMyName (wmn-data.json, 700+ сайтов) и кладёт его
рядом для глубокого режима username-энричера (USERNAME_DEEP=1).

Источник: community-датасет Micah Hoffman (WebBreacher/WhatsMyName) — детект-основа
многих username-OSINT-тулз. Содержит для каждого сайта URL-шаблон и правила
«найдено/не найдено» (e_string/e_code, m_string/m_code) + категорию.

Файл сохраняется в scripts/wmn-data.json (в .gitignore — это внешний артефакт, не код).

Использование:
    python fetch_wmn.py            # скачать / обновить датасет
    python fetch_wmn.py --info     # показать, что уже скачано (сайтов, категории)

Зависимости: requests. Источник можно переопределить через --url.
"""
import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    sys.exit("Нужен пакет requests: pip install -r requirements.txt")

RAW_URL = "https://raw.githubusercontent.com/WebBreacher/WhatsMyName/main/wmn-data.json"
SOURCE_REPO = "https://github.com/WebBreacher/WhatsMyName"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "wmn-data.json")


def info():
    if not os.path.exists(OUT):
        print("Датасет не скачан. Запусти: python fetch_wmn.py")
        return
    with open(OUT, encoding="utf-8") as f:
        data = json.load(f)
    sites = data.get("sites", [])
    cats = Counter(s.get("cat", "—") for s in sites)
    print(f"Файл: {OUT}")
    print(f"Сайтов: {len(sites)}  Категорий: {len(cats)}")
    print(f"Скачано: {data.get('_fetched_at', '—')}")
    print("\nТоп категорий:")
    for cat, n in cats.most_common(15):
        print(f"  {cat}: {n}")


def fetch(url):
    print(f"Загрузка {url} …")
    r = requests.get(url, headers={"User-Agent": "osint-wmn/1.0"}, timeout=60)
    r.raise_for_status()
    data = r.json()
    sites = data.get("sites", [])
    if not sites:
        sys.exit("Неожиданный формат: нет ключа 'sites'.")
    data["_fetched_at"] = datetime.now(timezone.utc).isoformat()
    data["_source"] = url
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"Готово: {len(sites)} сайтов → {OUT}")
    print("Глубокий режим: USERNAME_DEEP=1 python enrich.py username <ник>")


def main():
    ap = argparse.ArgumentParser(description="Скачать датасет WhatsMyName для deep-режима")
    ap.add_argument("--url", default=RAW_URL, help="raw URL wmn-data.json")
    ap.add_argument("--info", action="store_true", help="показать скачанный датасет")
    args = ap.parse_args()
    if args.info:
        info()
        return
    fetch(args.url)


if __name__ == "__main__":
    main()
