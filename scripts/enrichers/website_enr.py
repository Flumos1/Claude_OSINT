"""
Website-энричер (нейтральный) — анализ сайта в стиле web-check (lissy93).

Активные проверки (делают HTTP/TLS-запрос К САЙТУ — это «активный» сбор, оставляет след;
см. opsec.md, для подозрительных целей используй urlscan вместо прямого захода):
security-заголовки, SSL-сертификат (издатель/срок/SAN), сервер/тех-стек, цепочка редиректов,
наличие robots.txt и security.txt. Даёт security-оценку.
"""
import socket
import ssl
from datetime import datetime, timezone

import requests

from .base import EnricherResult, enricher

TIMEOUT = 12
UA = {"User-Agent": "Mozilla/5.0 (compatible; osint-website/1.0)"}
SEC_HEADERS = [
    "strict-transport-security", "content-security-policy", "x-frame-options",
    "x-content-type-options", "referrer-policy", "permissions-policy",
]


def _ssl_cert(host):
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=TIMEOUT) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as s:
                c = s.getpeercert()
        issuer = dict(x[0] for x in c.get("issuer", [])).get("organizationName", "?")
        not_after = c.get("notAfter")
        sans = [v for k, v in c.get("subjectAltName", []) if k == "DNS"]
        days = None
        if not_after:
            exp = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
            days = (exp - datetime.now(timezone.utc)).days
        return {"issuer": issuer, "expires": not_after, "days_left": days, "sans": sans}
    except Exception as e:
        return {"error": str(e)}


@enricher("website", "domain")
def enrich_website(value: str) -> EnricherResult:
    res = EnricherResult("website", "domain", value)
    host = value.strip().lower().lstrip("/")
    root = res.node("domain", host)
    res.fact("⚠️ Активные проверки (прямой запрос к сайту) — оставляют след. "
             "Для подозрительных целей используй urlscan/Wayback.", "opsec")

    # SSL
    cert = _ssl_cert(host)
    if not cert.get("error"):
        warn = " ⚠️истекает" if (cert.get("days_left") or 99) < 30 else ""
        res.fact(f"SSL: издатель {cert['issuer']}, действует до {cert['expires']} "
                 f"({cert['days_left']} дн.){warn}", "TLS", "B2")
        root.attrs["ssl_issuer"] = cert["issuer"]
        for s in cert.get("sans", [])[:8]:
            if s != host and not s.startswith("*"):
                n = res.node("domain", s, role="cert_san")
                res.edge(root, n, "cert_san")
    else:
        res.fact(f"SSL: ошибка ({cert['error']})", "TLS")

    # HTTP headers + redirects
    try:
        r = requests.get(f"https://{host}", headers=UA, timeout=TIMEOUT, allow_redirects=True)
        if r.history:
            chain = " → ".join([h.url for h in r.history] + [r.url])
            res.fact(f"Редиректы: {chain}", "HTTP")
        present = [h for h in SEC_HEADERS if h in {k.lower() for k in r.headers}]
        missing = [h for h in SEC_HEADERS if h not in present]
        grade = ["F", "E", "D", "C", "B", "A", "A+"][min(len(present), 6)]
        res.fact(f"Security-заголовки: {len(present)}/6 (оценка {grade}). "
                 f"Нет: {', '.join(missing) or '—'}", "HTTP", "B2")
        root.attrs["sec_grade"] = grade
        server = r.headers.get("Server") or r.headers.get("server")
        powered = r.headers.get("X-Powered-By")
        if server or powered:
            res.fact(f"Сервер/стек: {server or '—'}{' / ' + powered if powered else ''}", "HTTP", "C3")
    except Exception as e:
        res.fact(f"HTTP: ошибка ({e})", "HTTP")

    # robots / security.txt
    for path, label in [("/robots.txt", "robots.txt"), ("/.well-known/security.txt", "security.txt")]:
        try:
            rr = requests.get(f"https://{host}{path}", headers=UA, timeout=TIMEOUT)
            if rr.status_code == 200 and rr.text.strip():
                res.fact(f"{label}: есть ({len(rr.text)} б) — {host}{path}", "HTTP")
        except Exception:
            pass
    return res
