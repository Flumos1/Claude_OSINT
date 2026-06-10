"""
Opendatabot-энричер (UA) — живые данные из госреестров Украины через Opendatabot API.

Каркас, готовый к подключению API-ключа (его подключаем позже):
- Ключ берётся из окружения/.env: ODB_API_KEY (+ опц. ODB_API_BASE, ODB_API_VERSION).
- Без ключа энричер не падает, а возвращает инструкцию + deep-ссылку (no-key режим).
- Эндпоинты подтверждай по docs.opendatabot.com (база настраивается через ODB_API_BASE).

По ЄДРПОУ запрашивает карточку компании (CompanyService). Расширяемо на CourtService
(судові рішення), PenaltyService (ЄРБ/виконавчі), RealEstateService и др.
"""
import os

import requests

from .base import EnricherResult, enricher

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except Exception:
    pass

API_BASE = os.getenv("ODB_API_BASE", "https://opendatabot.com/api")
API_VERSION = os.getenv("ODB_API_VERSION", "v3")
TIMEOUT = 20


@enricher("opendatabot", "company", country="ua")
def enrich_opendatabot(value: str) -> EnricherResult:
    res = EnricherResult("opendatabot", "company", value)
    code = value.strip().replace(" ", "")
    root = res.node("company", code, country="ua")

    key = os.getenv("ODB_API_KEY")
    if not key:
        res.fact("Opendatabot API-ключ не задано (ODB_API_KEY у scripts/.env) — режим без ключа. "
                 "Перевір вручну/через UI.", "config")
        res.fact(f"Картка компанії: https://opendatabot.ua/c/{code}", "deep-link")
        return res

    if not (code.isdigit() and len(code) == 8):
        res.fact(f"Очікується ЄДРПОУ (8 цифр), отримано «{code}» — пропуск API-запиту.", "opendatabot")
        return res

    url = f"{API_BASE}/{API_VERSION}/company/{code}"
    try:
        r = requests.get(url, params={"apiKey": key}, timeout=TIMEOUT,
                         headers={"User-Agent": "osint-odb-enricher/1.0"})
        if r.status_code != 200:
            res.error = f"HTTP {r.status_code} ({url})"
            return res
        data = r.json()
        c = data.get("company", data)
        root.attrs.update({
            "name": c.get("full_name") or c.get("name"),
            "status": c.get("status_text") or c.get("status"),
            "address": c.get("address"),
            "kved": c.get("kved"),
        })
        res.fact(f"Назва: {root.attrs.get('name')}", "opendatabot API", "B2")
        res.fact(f"Статус: {root.attrs.get('status')}; адреса: {root.attrs.get('address')}",
                 "opendatabot API", "B2")
        for b in (c.get("beneficiaries") or []):
            bn = res.node("person", b.get("name", "?"), role="beneficiary", country="ua")
            res.edge(bn, root, "beneficiary_of")
            res.fact(f"Бенефіціар: {b.get('name')}", "opendatabot API", "B2")
        for d in (c.get("directors") or ([c["director"]] if c.get("director") else [])):
            name = d.get("name") if isinstance(d, dict) else d
            dn = res.node("person", name, role="director", country="ua")
            res.edge(dn, root, "director_of")
    except Exception as e:
        res.error = str(e)
    return res
