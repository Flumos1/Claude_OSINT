"""
Энричер archive_page — история веб-архива через Wayback CDX API (keyless).

web.archive.org/cdx — БЕЗ КЛЮЧА: отдаёт снапшоты URL/домена (первый/последний, число,
статусы, MIME). Пассивно, объект не видит запрос. Даёт таймлайн жизни ресурса —
важно для фактчекинга (когда появился/менялся контент) и атрибуции фишинга.

Работает и для url, и для domain (для домена — префиксный обзор поддоменов/страниц).
"""
import requests

from .base import EnricherResult, enricher

CDX = "http://web.archive.org/cdx/search/cdx"
TIMEOUT = 25
UA = {"User-Agent": "osint-archive/1.0"}


def _wayback(res: EnricherResult, root, target: str, domain_mode: bool) -> None:
    params = {"url": (target + "/*") if domain_mode else target,
              "output": "json", "fl": "timestamp,original,statuscode,mimetype",
              "collapse": "digest", "limit": "1000"}
    try:
        r = requests.get(CDX, params=params, headers=UA, timeout=TIMEOUT)
        if r.status_code != 200:
            res.error = f"HTTP {r.status_code} (wayback cdx)"
            return
        rows = r.json()
        if not rows or len(rows) < 2:
            res.fact("Wayback: снапшотів не знайдено (ресурс не архівувався).", "web.archive.org")
            return
        data = rows[1:]  # rows[0] — заголовки
        first, last = data[0][0], data[-1][0]
        def fmt(ts):
            return f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
        root.attrs.update({"wayback_snapshots": len(data),
                           "wayback_first": fmt(first), "wayback_last": fmt(last)})
        res.fact(f"Wayback: {len(data)} снапшотів; перший {fmt(first)}, останній {fmt(last)}",
                 "web.archive.org CDX", "B2")
        res.fact(f"Таймлайн-ключ: ресурс зафіксовано з {fmt(first)} — вік/поява контенту.",
                 "web.archive.org", "B3")
        if domain_mode:
            origins = {row[1] for row in data}
            res.fact(f"Унікальних URL під доменом в архіві: {len(origins)}", "web.archive.org", "C3")
        res.fact(f"Перегляд архіву: https://web.archive.org/web/*/{target}", "deep-link")
    except Exception as e:
        res.error = str(e)


@enricher("archive_page", "url")
def enrich_archive_url(value: str) -> EnricherResult:
    res = EnricherResult("archive_page", "url", value)
    root = res.node("url", value.strip())
    _wayback(res, root, value.strip(), domain_mode=False)
    return res


@enricher("archive_site", "domain")
def enrich_archive_domain(value: str) -> EnricherResult:
    res = EnricherResult("archive_site", "domain", value)
    root = res.node("domain", value.strip().lower())
    _wayback(res, root, value.strip().lower(), domain_mode=True)
    return res
