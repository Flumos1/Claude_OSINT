"""
Энричер архива — ближайший снимок страницы в Wayback Machine (keyless).

Сохранение доказательств на момент сбора — золотое правило (CLAUDE.md). Если снимка
нет, подсказывает как сохранить (web.archive.org/save/<url>).
"""
import requests

from .base import EnricherResult, enricher

TIMEOUT = 15
UA = {"User-Agent": "osint-archive/1.0"}


@enricher("archive", "url")
def enrich_archive(value: str) -> EnricherResult:
    res = EnricherResult("archive", "url", value)
    root = res.node("url", value)
    try:
        r = requests.get("http://archive.org/wayback/available", params={"url": value},
                         headers=UA, timeout=TIMEOUT)
        snap = ((r.json().get("archived_snapshots") or {}).get("closest") or {})
        if snap.get("available"):
            res.fact(f"Wayback: ближайший снимок {snap.get('timestamp')} → {snap.get('url')}",
                     "web.archive.org", "B2")
            root.attrs["wayback"] = snap.get("url")
            root.attrs["wayback_ts"] = snap.get("timestamp")
        else:
            res.fact(f"Wayback: снимков нет. Сохрани на момент сбора: "
                     f"https://web.archive.org/save/{value}", "web.archive.org")
    except Exception as e:
        res.error = str(e)
    return res
