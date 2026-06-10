"""
Email-leaks энричер (нейтральный) — присутствие email в известных утечках через HIBP.

Key-gated: нужен HIBP_API_KEY (.env). HIBP даёт ФАКТ компрометации (в каких breach'ах
засветился адрес) — для осведомлённости/смены паролей, НЕ выдаёт пароли/данные.
Этично: работай со своими/авторизованными адресами (см. ethics-legal.md).
Без ключа — graceful: подсказка + ссылка на ручную проверку.
"""
import os

import requests

from .base import EnricherResult, enricher

API = "https://haveibeenpwned.com/api/v3/breachedaccount/"
TIMEOUT = 20


@enricher("email_leaks", "email")
def enrich_email_leaks(value: str) -> EnricherResult:
    res = EnricherResult("email_leaks", "email", value)
    email = value.strip().lower()
    res.node("email", email)

    key = os.getenv("HIBP_API_KEY")
    if not key:
        res.fact("HIBP_API_KEY не задан — режим без ключа. Ручная проверка: "
                 f"https://haveibeenpwned.com/account/{email}", "config")
        return res

    try:
        r = requests.get(API + email, params={"truncateResponse": "false"},
                         headers={"hibp-api-key": key, "User-Agent": "osint-hibp/1.0"}, timeout=TIMEOUT)
        if r.status_code == 404:
            res.fact("В известных утечках (HIBP) не найден.", "HIBP API", "B2")
        elif r.status_code == 200:
            breaches = r.json()
            res.fact(f"Найден в {len(breaches)} утечках (HIBP).", "HIBP API", "B2")
            for b in breaches[:15]:
                classes = ", ".join(b.get("DataClasses", [])[:5])
                res.fact(f"{b.get('Name')} ({b.get('BreachDate')}): {classes}", "HIBP API", "B2")
        else:
            res.error = f"HTTP {r.status_code}"
    except Exception as e:
        res.error = str(e)
    return res
