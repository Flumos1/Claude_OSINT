#!/usr/bin/env python3
"""
dorks.py — генератор поисковых дорков (Google/Bing/Yandex) для домена и персоны.

Дорки = готовые запросы для поиска утечек файлов, открытых директорий, секретов,
упоминаний. Легально (это просто запросы к поисковику). Не делает запросов сам —
выдаёт готовые URL для ручного просмотра.

CLI:
    python dorks.py domain example.com
    python dorks.py person "Прізвище Ім'я"
"""
import sys
from urllib.parse import quote

ENGINES = {
    "google": "https://www.google.com/search?q=",
    "bing": "https://www.bing.com/search?q=",
    "yandex": "https://yandex.com/search/?text=",
    "duckduckgo": "https://duckduckgo.com/?q=",
}


def _url(query, engine="google"):
    return ENGINES[engine] + quote(query)


def domain_dorks(d: str) -> list[dict]:
    d = d.strip().lower().lstrip("/")
    raw = [
        ("Документы", f'site:{d} (filetype:pdf OR filetype:xlsx OR filetype:docx OR filetype:csv)'),
        ("Конфиги/секреты", f'site:{d} (ext:env OR ext:ini OR ext:yml OR ext:conf OR ext:sql OR ext:bak)'),
        ("Открытые директории", f'site:{d} intitle:"index of"'),
        ("Админки/входы", f'site:{d} (inurl:admin OR inurl:login OR inurl:dashboard OR inurl:wp-admin)'),
        ("Поддомены (искл. www)", f'site:*.{d} -www'),
        ("Утечки паролей/ключей", f'site:{d} (intext:password OR intext:api_key OR intext:secret OR intext:token)'),
        ("Корп. почты", f'site:{d} intext:"@{d}"'),
        ("Git/исходники", f'site:{d} (inurl:.git OR inurl:.svn OR inurl:wp-config)'),
        ("Облака/пасты", f'(site:s3.amazonaws.com OR site:trello.com OR site:pastebin.com OR site:github.com) {d}'),
        ("Google Docs/Drive", f'(site:docs.google.com OR site:drive.google.com) {d}'),
    ]
    return [{"label": l, "query": q, "url": _url(q)} for l, q in raw]


def person_dorks(name: str) -> list[dict]:
    n = name.strip()
    raw = [
        ("Резюме/CV", f'"{n}" (resume OR CV OR biography OR резюме)'),
        ("Соцсети", f'"{n}" (site:linkedin.com OR site:facebook.com OR site:t.me OR site:vk.com)'),
        ("Документы", f'"{n}" filetype:pdf'),
        ("Контакты", f'"{n}" (email OR phone OR контакт OR телефон)'),
        ("Почты", f'"{n}" (intext:"@gmail.com" OR intext:"@ukr.net" OR intext:"@mail.ru")'),
        ("Упоминания в пастах", f'"{n}" (site:pastebin.com OR site:justpaste.it)'),
        ("Объявления", f'"{n}" (site:olx.ua OR site:avito.ru)'),
    ]
    return [{"label": l, "query": q, "url": _url(q)} for l, q in raw]


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("domain", "person"):
        sys.exit("Использование: python dorks.py domain <домен> | person <ФИО>")
    kind, value = sys.argv[1], " ".join(sys.argv[2:])
    dorks = domain_dorks(value) if kind == "domain" else person_dorks(value)
    print(f"\nДорки для {kind}: {value}\n")
    for d in dorks:
        print(f"[{d['label']}]")
        print(f"  {d['query']}")
        print(f"  {d['url']}\n")


if __name__ == "__main__":
    main()
