"""
ProZorro-энричер (UA) — згадування компанії в держзакупівлях.
Відкрите API (БЕЗ ключа): POST prozorro.gov.ua/api/search/tenders {"text": <ЄДРПОУ>}.

Пошук за кодом знаходить тендери, де код фігурує як замовник АБО учасник — тому це
«згадування»; роль уточнюй у картці тендера. ProZorro — дуже прозоре джерело.
"""
import requests

from .base import EnricherResult, enricher

API = "https://prozorro.gov.ua/api/search/tenders"
TIMEOUT = 25


@enricher("prozorro", "company", country="ua")
def enrich_prozorro(value: str) -> EnricherResult:
    res = EnricherResult("prozorro", "company", value)
    code = value.strip().replace(" ", "")
    res.node("company", code, country="ua")
    try:
        r = requests.post(API, json={"text": code},
                          headers={"User-Agent": "osint-prozorro-enricher/1.0",
                                   "Content-Type": "application/json"}, timeout=TIMEOUT)
        if r.status_code != 200:
            res.error = f"HTTP {r.status_code}"
            return res
        d = r.json()
        total = d.get("total", 0)
        items = d.get("data", [])
        res.fact(f"Згадувань у тендерах ProZorro за кодом {code}: {total}", "ProZorro API", "B2")
        for it in items[:6]:
            pe = (it.get("procuringEntity", {}) or {}).get("identifier", {})
            title = (it.get("title") or "").strip()[:90]
            val = it.get("value", {}) or {}
            amount = f"{val.get('amount')} {val.get('currency')}" if val.get("amount") else ""
            res.fact(f"{it.get('tenderID')}: {title} | замовник: {pe.get('legalName')} | "
                     f"{it.get('status')} {amount}".strip(), "ProZorro API", "B2")
        if total > 6:
            res.fact(f"… ще {total - 6}. Пошук: https://prozorro.gov.ua/search/tenders?text={code}",
                     "ProZorro")
    except Exception as e:
        res.error = str(e)
    return res
