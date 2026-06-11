"""
Opendatabot-энричер (UA) — живые данные из госреестров Украины через Opendatabot API.

Каркас, готовый к подключению API-ключа:
- Ключ берётся из окружения/.env: ODB_API_KEY (+ опц. ODB_API_BASE, ODB_API_VERSION).
- Без ключа энричер не падает, а возвращает инструкцию + deep-ссылку (no-key режим).
  Полный набор deep-ссылок на реестры (суди/боржники/виконавчі) даёт `ua_company_links`.

По ЄДРПОУ запрашивает карточку компании (CompanyService) и — опционально — доп. сервисы
(судові рішення / виконавчі-штрафи / нерухомість). URL доп. сервисов заданы ШАБЛОНАМИ
по умолчанию и ПЕРЕОПРЕДЕЛЯЕМЫ через env (ODB_URL_COURT/ODB_URL_FINES/ODB_URL_REALTY) —
точные пути подтверди по docs.opendatabot.com. Каждый доп. вызов устойчив (не фатален).
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
HEADERS = {"User-Agent": "osint-odb-enricher/1.0"}

# Доп. сервисы: (ключ, ярлык, URL-шаблон по умолчанию, подсказки-ключи для счётчика).
# Шаблоны форматируются {base}/{ver}/{code}. Дефолтные пути НЕПОДТВЕРЖДЕНЫ — при наличии
# ключа подтверди/переопредели через env (ODB_URL_COURT и т.д.) по docs.opendatabot.com.
EXTRA_SERVICES = [
    ("court", "Судові рішення",
     os.getenv("ODB_URL_COURT", "{base}/{ver}/court/{code}"),
     ("count", "total", "items", "records", "decisions")),
    ("fines", "Виконавчі провадження / штрафи",
     os.getenv("ODB_URL_FINES", "{base}/{ver}/fines/{code}"),
     ("count", "total", "items", "records", "penalties")),
    ("realty", "Нерухомість",
     os.getenv("ODB_URL_REALTY", "{base}/{ver}/realty/{code}"),
     ("count", "total", "items", "records", "objects")),
]


def _count(data, hints) -> int | None:
    """Достать число записей из ответа: по подсказкам-ключам или длине первого списка."""
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for h in hints:
            v = data.get(h)
            if isinstance(v, int):
                return v
            if isinstance(v, list):
                return len(v)
        for v in data.values():
            if isinstance(v, list):
                return len(v)
    return None


def _items(data, hints) -> list:
    """Достать список записей (для образцов узлов)."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for h in hints:
            v = data.get(h)
            if isinstance(v, list):
                return v
        for v in data.values():
            if isinstance(v, list):
                return v
    return []


def _extra_services(res: EnricherResult, code: str, key: str) -> None:
    """Опрос доп. сервисов Opendatabot. Каждый вызов устойчив; пути подтверждаются по докам."""
    failed = []
    for sid, label, tpl, hints in EXTRA_SERVICES:
        url = tpl.format(base=API_BASE, ver=API_VERSION, code=code)
        try:
            r = requests.get(url, params={"apiKey": key}, timeout=TIMEOUT, headers=HEADERS)
            if r.status_code != 200:
                failed.append(sid)
                continue
            data = r.json()
            n = _count(data, hints)
            res.fact(f"{label}: {n if n is not None else '?'} записів", "opendatabot API", "B2")
            for it in _items(data, hints)[:5]:
                if not isinstance(it, dict):
                    continue
                title = it.get("number") or it.get("title") or it.get("name") or it.get("date")
                if title:
                    res.fact(f"  • {label}: {title}", "opendatabot API", "C3")
        except Exception:
            failed.append(sid)
    if len(failed) == len(EXTRA_SERVICES):
        res.fact("Доп. сервіси (court/fines/realty) не відповіли за поточними шляхами — "
                 "підтверди ODB_URL_COURT/ODB_URL_FINES/ODB_URL_REALTY за docs.opendatabot.com.",
                 "config")


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
        r = requests.get(url, params={"apiKey": key}, timeout=TIMEOUT, headers=HEADERS)
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

    _extra_services(res, code, key)
    return res
