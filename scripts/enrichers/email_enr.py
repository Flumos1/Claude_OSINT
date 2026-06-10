"""
Энричер email — keyless: Gravatar (профиль/аватар) + разбор домена.
Утечки (HIBP) НЕ включены: требуют API-ключ и работают только по своим/авторизованным
адресам (см. ethics-legal.md). Когда будет ключ — отдельный энричер breach_hibp.
"""
import hashlib

import requests

from .base import EnricherResult, enricher

TIMEOUT = 15


@enricher("email_gravatar", "email")
def enrich_email(value: str) -> EnricherResult:
    res = EnricherResult("email_gravatar", "email", value)
    email = value.strip().lower()
    root = res.node("email", email)

    # домен email -> узел домена (пивот в domain_recon)
    if "@" in email:
        domain = email.split("@", 1)[1]
        dn = res.node("domain", domain, role="email_domain")
        res.edge(root, dn, "email_domain")

    h = hashlib.md5(email.encode()).hexdigest()
    try:
        r = requests.get(
            f"https://gravatar.com/{h}.json",
            headers={"User-Agent": "osint-email-enricher/1.0"},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            entry = (r.json().get("entry") or [{}])[0]
            display = entry.get("displayName") or entry.get("preferredUsername")
            root.attrs["gravatar"] = f"https://gravatar.com/{h}"
            res.fact(f"Есть Gravatar-профиль: {display or h}", "gravatar.com", "C2")
            for acc in entry.get("accounts", []):
                url = acc.get("url")
                if url:
                    un = res.node("username", acc.get("username") or url, platform=acc.get("shortname"))
                    res.edge(root, un, "linked_account")
                    res.fact(f"Связанный аккаунт: {acc.get('shortname')} {url}", "gravatar.com", "C3")
            if display:
                pn = res.node("person", display, via="gravatar")
                res.edge(root, pn, "possibly_belongs_to")
        else:
            res.fact("Gravatar-профиль не найден (адрес может быть валиден без него)", "gravatar.com")
    except Exception as e:
        res.error = str(e)
    return res
