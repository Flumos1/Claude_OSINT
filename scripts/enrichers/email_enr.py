"""
Энричер email — keyless: Gravatar (профиль/аватар) + разбор домена.
Утечки (HIBP) НЕ включены: требуют API-ключ и работают только по своим/авторизованным
адресам (см. ethics-legal.md). Когда будет ключ — отдельный энричер breach_hibp.
"""
import hashlib
import os
import sys

import requests

from .base import EnricherResult, enricher

TIMEOUT = 15

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from image_tools import ahash, reverse_image_links
except Exception:
    ahash = reverse_image_links = None


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
            # аватар → reverse-image ссылки + опц. aHash (сверка лица между платформами)
            if reverse_image_links is not None:
                av = f"https://gravatar.com/avatar/{h}?s=256"
                img = res.node("url", av, kind="avatar")
                res.edge(root, img, "avatar")
                ph = ahash(av) if ahash else None
                if ph:
                    img.attrs["ahash"] = ph
                    res.fact(f"Аватар aHash={ph} (для звірки облич)", "image_tools", "C3")
                res.fact("Reverse-image: " + " | ".join(
                    f"{k}: {v}" for k, v in reverse_image_links(av).items()), "image_tools")
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
