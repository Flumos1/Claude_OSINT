"""
Энричер email → регистрации (holehe-стиль, но ЭТИЧНО и keyless).

Принцип: используем только БЕЗОПАСНЫЕ, штатные публичные сигналы существования аккаунта
(не «долбим» password-reset/signup — это ToS-серо и вне наших рамок, см. ethics-legal.md):
  • Gravatar/Libravatar — штатный публичный чек «есть ли аватар» (?d=404): 200=есть, 404=нет.
Для более глубокой проверки (holehe/epieos) даём tool-пивот — оператор запускает осознанно.

Возвращает: узел email, факты о найденных публичных профилях-по-email + ссылки на инструменты.
"""
import hashlib

import requests

from .base import EnricherResult, enricher

TIMEOUT = 12
UA = {"User-Agent": "osint-email-accounts/1.0"}


def _exists(url: str) -> bool | None:
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT, allow_redirects=False)
        if r.status_code == 200:
            return True
        if r.status_code in (404, 302, 301):
            return False
    except Exception:
        return None
    return None


@enricher("email_accounts", "email")
def enrich_email_accounts(value: str) -> EnricherResult:
    res = EnricherResult("email_accounts", "email", value)
    email = value.strip().lower()
    root = res.node("email", email)
    if "@" not in email:
        res.fact("Не похоже на email — пропуск.", "email_accounts")
        return res

    h = hashlib.md5(email.encode()).hexdigest()
    found = []
    # Gravatar — штатный публичный existence-чек
    g = _exists(f"https://gravatar.com/avatar/{h}?d=404")
    if g:
        found.append("Gravatar")
        res.fact("Email зареєстровано в Gravatar (штатний ?d=404 → 200)", "gravatar.com", "C2")
    # Libravatar — открытый аналог
    lv = _exists(f"https://seccdn.libravatar.org/avatar/{h}?d=404")
    if lv:
        found.append("Libravatar")
        res.fact("Email зареєстровано в Libravatar", "libravatar.org", "C3")

    res.fact(f"Публічні існування-сигнали за email: {', '.join(found) or '—'} "
             f"(безпечні, штатні; не reset-проби).", "email_accounts")

    # tool-пивот для глубокой проверки (осознанно, по ToS)
    res.fact("Глибша перевірка реєстрацій (holehe/epieos) — запускай осмислено, "
             "в межах ToS/закону: epieos.com, github.com/megadose/holehe.", "tools-catalog")
    res.fact("⚠️ Ми не «пробиваємо» reset/signup ендпоінти сервісів — це проти "
             "ethics-legal.md. Тільки штатні публічні сигнали.", "ethics-legal")
    return res
