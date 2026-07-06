"""
Энричер истории домена — SecurityTrails: текущие DNS, поддомены, базовый WHOIS.

Key-gated (SECURITYTRAILS_API_KEY, free-tier), graceful без ключа.
Дополняет domain_recon (crt.sh/RDAP) данными SecurityTrails (история/поддомены).
"""
import os

import requests

from .base import EnricherResult, enricher

TIMEOUT = 20
UA = {"User-Agent": "osint-domain-history/1.0"}
BASE = "https://api.securitytrails.com/v1"


@enricher("domain_history", "domain")
def enrich_domain_history(value: str) -> EnricherResult:
    res = EnricherResult("domain_history", "domain", value)
    dom = value.strip().lower()
    root = res.node("domain", dom)

    key = os.getenv("SECURITYTRAILS_API_KEY")
    if not key:
        res.fact("SECURITYTRAILS_API_KEY не задан — добавь в .env (free-tier). "
                 "Альтернатива без ключа: crt.sh + Wayback (энричер domain_recon).", "config")
        return res

    headers = {"APIKEY": key, "Accept": "application/json", **UA}
    try:
        r = requests.get(f"{BASE}/domain/{dom}", headers=headers, timeout=TIMEOUT)
        if r.status_code == 429:
            res.fact("SecurityTrails: лимит free-tier исчерпан — повтори позже.", "SecurityTrails API")
            return res
        if r.ok:
            d = r.json()
            cur = (d.get("current_dns") or {})
            a = ((cur.get("a") or {}).get("values") or [])
            for rec in a[:5]:
                ip = rec.get("ip")
                if ip:
                    n = res.node("ip", ip)
                    res.edge(root, n, "resolves_to")
            ns = ((cur.get("ns") or {}).get("values") or [])
            if ns:
                res.fact(f"NS: {', '.join(v.get('nameserver', '') for v in ns[:4])}",
                         "SecurityTrails API", "B2")
            if d.get("hostname"):
                root.attrs["hostname"] = d.get("hostname")
            res.fact(f"Поддоменов (SecurityTrails): {d.get('subdomain_count', '—')}",
                     "SecurityTrails API", "B2")
        else:
            res.fact(f"SecurityTrails domain: HTTP {r.status_code}.", "SecurityTrails API")

        rs = requests.get(f"{BASE}/domain/{dom}/subdomains", headers=headers,
                          params={"children_only": "true"}, timeout=TIMEOUT)
        if rs.ok:
            subs = rs.json().get("subdomains", []) or []
            for s in subs[:25]:
                n = res.node("domain", f"{s}.{dom}", role="subdomain")
                res.edge(n, root, "subdomain_of")
            if subs:
                res.fact(f"Найдено поддоменов: {len(subs)} (показаны до 25).", "SecurityTrails API", "B2")
    except Exception as e:
        res.error = str(e)
    return res
