#!/usr/bin/env python3
"""
domain_recon.py — быстрая пассивная разведка по домену из открытых источников.

Собирает: RDAP (регистрация), crt.sh (поддомены из Certificate Transparency),
DNS-записи (A/AAAA/MX/NS/TXT), наличие в Wayback Machine.

Только пассивные публичные источники — объект не получает прямого запроса от вас
(кроме DNS-резолва). Соблюдайте OPSEC и законность (см. knowledge/opsec.md, ethics-legal.md).

Использование:
    python domain_recon.py example.com
    python domain_recon.py example.com --json out.json

Зависимости: requests (pip install -r requirements.txt). DNS — опционально dnspython
(если нет, MX/NS/TXT пропускаются, A-запись берётся через socket).
"""
import argparse
import json
import socket
import sys
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    sys.exit("Нужен пакет requests: pip install -r requirements.txt")

try:
    import dns.resolver  # dnspython
    HAVE_DNS = True
except ImportError:
    HAVE_DNS = False

UA = {"User-Agent": "osint-domain-recon/1.0"}
TIMEOUT = 20


def rdap(domain):
    """Регистрационные данные через rdap.org (RDAP — преемник WHOIS)."""
    try:
        r = requests.get(f"https://rdap.org/domain/{domain}", headers=UA, timeout=TIMEOUT)
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}"}
        d = r.json()
        events = {e.get("eventAction"): e.get("eventDate") for e in d.get("events", [])}
        ns = [n.get("ldhName") for n in d.get("nameservers", [])]
        registrar = None
        for ent in d.get("entities", []):
            if "registrar" in ent.get("roles", []):
                registrar = ent.get("vcardArray", [None, []])[1]
        return {
            "handle": d.get("handle"),
            "status": d.get("status"),
            "registered": events.get("registration"),
            "expires": events.get("expiration"),
            "last_changed": events.get("last changed"),
            "nameservers": ns,
            "registrar_vcard": registrar,
        }
    except Exception as e:
        return {"error": str(e)}


def crtsh(domain):
    """Поддомены из Certificate Transparency через crt.sh."""
    try:
        r = requests.get(
            f"https://crt.sh/?q=%25.{domain}&output=json", headers=UA, timeout=TIMEOUT
        )
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}"}
        names = set()
        for row in r.json():
            for n in row.get("name_value", "").splitlines():
                n = n.strip().lower().lstrip("*.")
                if n.endswith(domain):
                    names.add(n)
        return sorted(names)
    except Exception as e:
        return {"error": str(e)}


def dns_records(domain):
    out = {}
    if HAVE_DNS:
        for rtype in ("A", "AAAA", "MX", "NS", "TXT"):
            try:
                ans = dns.resolver.resolve(domain, rtype, lifetime=TIMEOUT)
                out[rtype] = [r.to_text() for r in ans]
            except Exception:
                out[rtype] = []
    else:
        try:
            out["A"] = sorted({ai[4][0] for ai in socket.getaddrinfo(domain, None)})
        except Exception:
            out["A"] = []
        out["_note"] = "dnspython не установлен — только A-запись. pip install dnspython"
    return out


def wayback(domain):
    """Есть ли архивные снимки в Wayback Machine."""
    try:
        r = requests.get(
            "http://archive.org/wayback/available",
            params={"url": domain},
            headers=UA,
            timeout=TIMEOUT,
        )
        snap = r.json().get("archived_snapshots", {}).get("closest")
        return snap or {"available": False}
    except Exception as e:
        return {"error": str(e)}


def main():
    ap = argparse.ArgumentParser(description="Пассивная разведка по домену")
    ap.add_argument("domain")
    ap.add_argument("--json", metavar="FILE", help="сохранить результат в JSON")
    args = ap.parse_args()
    domain = args.domain.strip().lower()

    result = {
        "domain": domain,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "rdap": rdap(domain),
        "dns": dns_records(domain),
        "subdomains_crtsh": crtsh(domain),
        "wayback": wayback(domain),
    }

    subs = result["subdomains_crtsh"]
    print(f"\n=== {domain} === ({result['collected_at']})")
    reg = result["rdap"]
    print(f"\n[RDAP] создан: {reg.get('registered')}  истекает: {reg.get('expires')}")
    print(f"       NS: {', '.join(reg.get('nameservers') or []) or '—'}")
    print(f"\n[DNS] {json.dumps(result['dns'], ensure_ascii=False)}")
    n = len(subs) if isinstance(subs, list) else 0
    print(f"\n[crt.sh] поддоменов: {n}")
    for s in (subs[:40] if isinstance(subs, list) else []):
        print(f"   {s}")
    if n > 40:
        print(f"   … и ещё {n - 40}")
    wb = result["wayback"]
    print(f"\n[Wayback] {wb.get('timestamp', '—')} {wb.get('url', '')}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\nСохранено: {args.json}")


if __name__ == "__main__":
    main()
