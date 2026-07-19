"""
subfinder_enr.py — РЕАЛЬНЫЙ запуск subfinder (projectdiscovery/subfinder, MIT) по
домену: быстрый пассивный subdomain enumeration через десятки источников.

⚠️ Docker-only: subfinder — статический Go-бинарник, вшивается в образ на этапе
сборки (см. Dockerfile, скачивается из GitHub Releases). На Vercel/без Docker —
энричер отдаёт факт «недоступно» и не падает.

Работает keyless «из коробки» (крупные источники вроде crt.sh, DNS-based) —
для платных источников (Shodan, Censys и т.п.) нужен provider-config.yaml, вне
объёма этой интеграции.
"""
import os

from ._binhelper import find_bin, run_json_stdout, unavailable_fact
from .base import EnricherResult, enricher

TIMEOUT = int(os.getenv("SUBFINDER_TIMEOUT", "90"))
INSTALL_HINT = ("Docker-образ: скачан бінарник з GitHub Releases (див. Dockerfile). "
                "Вручну: go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest")


@enricher("subfinder", "domain")
def enrich_subfinder(value: str) -> EnricherResult:
    res = EnricherResult("subfinder", "domain", value)
    domain = value.strip().lower()
    root = res.node("domain", domain)

    binpath = find_bin("subfinder", "SUBFINDER_BIN")
    if not binpath:
        unavailable_fact(res, "subfinder", INSTALL_HINT)
        return res

    rows = run_json_stdout([binpath, "-d", domain, "-oJ", "-silent"], timeout=TIMEOUT, ndjson=True)
    if not rows:
        res.fact("subfinder: немає результату (таймаут/помилка запуску або джерела "
                 "нічого не дали).", "subfinder")
        return res

    seen = set()
    sources_used = set()
    for row in rows:
        host = (row.get("host") or "").strip().lower()
        if not host or host == domain or host in seen:
            continue
        seen.add(host)
        src = row.get("source", "?")
        sources_used.add(src)
        dn = res.node("domain", host, role="subdomain")
        res.edge(dn, root, "subdomain_of")
        res.fact(f"Піддомен: {host}", f"subfinder ({src})", "C3")

    res.fact(f"subfinder: {len(seen)} унікальних піддоменів "
             f"(джерела: {', '.join(sorted(sources_used)) or '—'}).", "subfinder", "C3")
    return res
