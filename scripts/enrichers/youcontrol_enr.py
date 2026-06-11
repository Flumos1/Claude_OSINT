"""
YouControl-энричер (UA) — карточка компании из YouControl/YouScore по ЄДРПОУ.

YouControl агрегирует ЄДР + суди + санкції + зв'язки/бенефіціари (сильная сторона —
графы связей и негативные факты). Хостинговый API (YouScore) требует ключ.

Каркас по образцу opendatabot_enr:
- Ключ: YOUCONTROL_API_KEY (+ опц. YOUCONTROL_API_BASE, YOUCONTROL_URL — шаблон) из .env.
- Без ключа — инструкция + надёжная deep-ссылка на картку YouControl (no-key режим).
- URL/структура ответа API подтверждаются по докам YouScore; вызов устойчив (не фатален),
  разбор полей обобщённый. Точный шаблон при необходимости задай через YOUCONTROL_URL.
"""
import os

import requests

from .base import EnricherResult, enricher

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except Exception:
    pass

API_BASE = os.getenv("YOUCONTROL_API_BASE", "https://api.youscore.com.ua")
# Шаблон URL запроса; форматируется {base}/{code}. НЕПОДТВЕРЖДЁН — подтверди по докам YouScore.
URL_TPL = os.getenv("YOUCONTROL_URL", "{base}/v1/company/{code}")
TIMEOUT = 20
HEADERS = {"User-Agent": "osint-youcontrol-enricher/1.0"}


def _deeplink(code: str) -> str:
    return f"https://youcontrol.com.ua/catalog/company_details/{code}/"


@enricher("youcontrol", "company", country="ua")
def enrich_youcontrol(value: str) -> EnricherResult:
    res = EnricherResult("youcontrol", "company", value)
    code = value.strip().replace(" ", "")
    root = res.node("company", code, country="ua")

    key = os.getenv("YOUCONTROL_API_KEY")
    if not key:
        res.fact("YouControl API-ключ не задано (YOUCONTROL_API_KEY у scripts/.env) — режим без ключа.",
                 "config")
        res.fact(f"Картка YouControl: {_deeplink(code)}", "deep-link")
        return res

    if not (code.isdigit() and len(code) == 8):
        res.fact(f"Очікується ЄДРПОУ (8 цифр), отримано «{code}» — пропуск API-запиту.", "youcontrol")
        res.fact(f"Картка YouControl: {_deeplink(code)}", "deep-link")
        return res

    url = URL_TPL.format(base=API_BASE, code=code)
    try:
        r = requests.get(url, headers={**HEADERS, "Authorization": f"Bearer {key}"}, timeout=TIMEOUT)
        if r.status_code != 200:
            res.error = f"HTTP {r.status_code} ({url}) — підтверди YOUCONTROL_URL/ключ за доками YouScore"
            res.fact(f"Картка YouControl: {_deeplink(code)}", "deep-link")
            return res
        data = r.json()
        c = data.get("company", data) if isinstance(data, dict) else {}
        root.attrs.update({
            "name": c.get("name") or c.get("full_name") or c.get("shortName"),
            "status": c.get("status") or c.get("state"),
            "kved": c.get("kved") or c.get("activityKind"),
            "address": c.get("address") or c.get("location"),
        })
        res.fact(f"Назва: {root.attrs.get('name')}; статус: {root.attrs.get('status')}",
                 "YouControl/YouScore API", "B2")
        for b in (c.get("beneficiaries") or c.get("founders") or []):
            name = b.get("name") if isinstance(b, dict) else b
            if not name:
                continue
            bn = res.node("person", name, role="beneficiary", country="ua")
            res.edge(bn, root, "beneficiary_of")
            res.fact(f"Бенефіціар/засновник: {name}", "YouControl/YouScore API", "B2")
    except Exception as e:
        res.error = str(e)
        res.fact(f"Картка YouControl: {_deeplink(code)}", "deep-link")
    return res
