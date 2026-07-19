"""
Энричер whois_history (domain) — история WHOIS-записей домена.

Историческая WHOIS (кто владел доменом раньше, смена регистранта/NS во времени) — почти
всегда платная (WhoisXML, SecurityTrails, DomainTools). Поэтому энричер честный:
  • без ключа — deep-ссылки на сервисы истории (ViewDNS, WhoisXML, SecurityTrails, Whoxy);
  • с ключом WHOISXML_API_KEY — живой запрос WhoisXML Whois History API (число записей,
    самая ранняя дата, регистранты во времени).
Текущий WHOIS/RDAP (дата регистрации, NS) даёт `domain_recon` — это дополнение по ИСТОРИИ.
"""
import os

import requests

from .base import EnricherResult, enricher

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except Exception:
    pass

# 25с одноосібно з'їдало значну частину бюджету при 9 послідовних domain-енричерах.
TIMEOUT = 12
UA = {"User-Agent": "osint-whois-history/1.0"}


def _history_links(domain: str) -> dict[str, str]:
    return {
        "ViewDNS WHOIS history": f"https://viewdns.info/whoishistory/?domain={domain}",
        "Whoxy history": f"https://www.whoxy.com/{domain}",
        "SecurityTrails": f"https://securitytrails.com/domain/{domain}/history/whois",
        "WhoisXML history": f"https://whois-history.whoisxmlapi.com/lookup?domainName={domain}",
    }


@enricher("whois_history", "domain")
def enrich_whois_history(value: str) -> EnricherResult:
    res = EnricherResult("whois_history", "domain", value)
    domain = value.strip().lower()
    root = res.node("domain", domain)

    key = os.getenv("WHOISXML_API_KEY")
    if key:
        try:
            r = requests.get("https://whois-history.whoisxmlapi.com/api/v1",
                             params={"apiKey": key, "domainName": domain, "mode": "purchase"},
                             headers=UA, timeout=TIMEOUT)
            if r.status_code == 200:
                d = r.json()
                recs = d.get("records") or []
                res.fact(f"WHOIS history: записів {d.get('recordsCount', len(recs))}",
                         "WhoisXML history API", "B2")
                registrants = []
                for rec in recs:
                    ra = (rec.get("registrantContact") or {})
                    nm = ra.get("organization") or ra.get("name")
                    when = rec.get("createdDateNormalized") or rec.get("auditUpdatedDate")
                    if nm:
                        registrants.append((when or "?", nm))
                for when, nm in registrants[:8]:
                    res.fact(f"  реєстрант ({when}): {nm}", "WhoisXML history API", "C3")
                if registrants:
                    uniq = {nm for _, nm in registrants}
                    if len(uniq) > 1:
                        res.fact(f"Реєстрант змінювався ({len(uniq)} різних) — можлива зміна власника.",
                                 "WhoisXML history API", "C2")
            else:
                res.fact(f"WhoisXML history: HTTP {r.status_code} (перевір ключ/квоту).", "config")
        except Exception as e:
            res.error = str(e)
    else:
        res.fact("WHOIS-історія — платні джерела (ключ WHOISXML_API_KEY не задано). "
                 "Без ключа — сервіси історії нижче:", "config")

    for name, url in _history_links(domain).items():
        res.fact(f"{name}: {url}", "deep-link")
    return res
