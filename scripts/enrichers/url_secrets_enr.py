"""
URL-секреты энричер (нейтральный) — скан страницы/бандла на утёкшие секреты.
Активный запрос к URL. Для защиты СВОИХ ассетов. Каталог паттернов — scripts/secrets_scan.py.
"""
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from secrets_scan import PATTERNS, scan  # noqa: E402

from .base import EnricherResult, enricher  # noqa: E402


@enricher("secrets_scan", "url")
def enrich_url_secrets(value: str) -> EnricherResult:
    res = EnricherResult("secrets_scan", "url", value)
    res.node("url", value)
    res.fact("⚠️ Активный запрос. Сканируй свои/авторизованные ассеты (защита).", "opsec")
    try:
        text = requests.get(value, headers={"User-Agent": "osint-secrets/1.0"}, timeout=20).text
        hits = scan(text)
        res.fact(f"Секретов найдено: {len(hits)} (паттернов: {len(PATTERNS)})",
                 "secrets_scan", "B2" if hits else "")
        for h in hits[:20]:
            res.fact(f"{h['type']}: {h['match']}", "secrets_scan", "B2")
    except Exception as e:
        res.error = str(e)
    return res
