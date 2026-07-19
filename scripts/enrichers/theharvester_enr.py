"""
theharvester_enr.py — РЕАЛЬНЫЙ запуск theHarvester (laramies/theHarvester, GPL-2.0)
по домену: email/поддомены/хосты/ASN через пассивные источники.

⚠️ Docker-only: theHarvester тянет свои жёстко закреплённые зависимости (включая
fastapi/uvicorn конкретных версий) — ставится в ИЗОЛИРОВАННЫЙ venv на этапе сборки
образа (см. Dockerfile), не в общее окружение приложения (риск конфликта версий).
На Vercel/без Docker бинарника нет — энричер отдаёт факт «недоступно» и не падает.

Источники по умолчанию — только KEYLESS (без API-ключей): crtsh, rapiddns,
hackertarget, subdomaincenter. Больше источников — задай THEHARVESTER_SOURCES
(см. `theHarvester -h` за полным списком; многим нужны свои API-ключи).
"""
import os

from ._binhelper import find_bin, run_json_file, temp_path, unavailable_fact
from .base import EnricherResult, enricher

TIMEOUT = int(os.getenv("THEHARVESTER_TIMEOUT", "120"))
SOURCES = os.getenv("THEHARVESTER_SOURCES", "crtsh,rapiddns,hackertarget,subdomaincenter")
INSTALL_HINT = ("Docker-образ: git clone + venv (см. Dockerfile). Вручную: "
                "git clone https://github.com/laramies/theHarvester && uv sync && uv run theHarvester")


@enricher("theharvester", "domain")
def enrich_theharvester(value: str) -> EnricherResult:
    res = EnricherResult("theharvester", "domain", value)
    domain = value.strip().lower()
    root = res.node("domain", domain)

    binpath = find_bin("theHarvester", "THEHARVESTER_BIN")
    if not binpath:
        unavailable_fact(res, "theHarvester", INSTALL_HINT)
        return res

    out_base = temp_path()
    data = run_json_file(
        [binpath, "-d", domain, "-b", SOURCES, "-f", out_base],
        out_path=out_base + ".json", timeout=TIMEOUT,
    )
    if data is None:
        res.fact("theHarvester: немає результату (таймаут/помилка запуску або джерела "
                 "не дали даних).", "theHarvester")
        return res

    emails = data.get("emails") or []
    hosts = data.get("hosts") or []
    ips = data.get("ips") or []
    asns = data.get("asns") or []

    for e in emails:
        en = res.node("email", e)
        res.edge(en, root, "found_via_domain")
        res.fact(f"Email знайдено: {e}", f"theHarvester ({SOURCES})", "C3")

    for h in hosts:
        # запись может быть "sub.domain.com" или "sub.domain.com:1.2.3.4"
        name = h.split(":", 1)[0] if ":" in h else h
        if not name or name == domain:
            continue
        dn = res.node("domain", name, role="subdomain")
        res.edge(dn, root, "subdomain_of")
        res.fact(f"Піддомен: {name}", f"theHarvester ({SOURCES})", "C3")

    for ip in ips:
        ipn = res.node("ip", ip)
        res.edge(root, ipn, "resolves_to")

    res.fact(f"theHarvester ({SOURCES}): emails={len(emails)}, хостів={len(hosts)}, "
             f"IP={len(ips)}, ASN={len(asns)}.", "theHarvester", "C3")
    return res
