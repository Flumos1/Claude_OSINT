"""
NAZK-энричер (UA) — декларації посадовців з Єдиного держреєстру декларацій.
Відкрите API НАЗК (БЕЗ ключа): public-api.nazk.gov.ua/v2/documents/list?query=<ПІБ>.

Декларації публічних осіб відкриті за законом — легально й без обмежень. Пошук за ПІБ
може повертати однофамільців: перевіряй посаду/рік перед атрибуцією.
"""
from urllib.parse import quote

import requests

from .base import EnricherResult, enricher

API = "https://public-api.nazk.gov.ua/v2/documents/list"
TIMEOUT = 20


@enricher("nazk_declarations", "person", country="ua")
def enrich_nazk(value: str) -> EnricherResult:
    res = EnricherResult("nazk_declarations", "person", value)
    name = value.strip()
    if name.replace(" ", "").isdigit():
        return res  # РНОКПП/число — не для пошуку декларацій за ПІБ

    res.node("person", name, country="ua")
    try:
        r = requests.get(API, params={"query": name, "page": 1},
                         headers={"User-Agent": "osint-nazk-enricher/1.0"}, timeout=TIMEOUT)
        if r.status_code != 200:
            res.error = f"HTTP {r.status_code}"
            return res
        d = r.json()
        count = d.get("count", 0)
        items = d.get("data", [])
        res.fact(f"Декларацій НАЗК за запитом «{name}»: {count} "
                 f"(увага: можливі однофамільці)", "НАЗК API", "B2")
        for it in items[:8]:
            s1 = (it.get("data", {}).get("step_1", {}) or {}).get("data", {})
            full = " ".join(filter(None, [s1.get("lastname"), s1.get("firstname"), s1.get("middlename")]))
            year = it.get("declaration_year")
            did = it.get("id")
            res.fact(f"{full or '?'} — декларація {year}: "
                     f"https://public.nazk.gov.ua/documents/{did}", "НАЗК API", "B2")
        if count > 8:
            res.fact(f"… ще {count - 8}. Усі: "
                     f"https://public.nazk.gov.ua/documents/list?query={quote(name)}", "НАЗК")
    except Exception as e:
        res.error = str(e)
    return res
