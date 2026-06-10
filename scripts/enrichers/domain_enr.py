"""Энричер домена — переиспользует функции domain_recon.py (RDAP, crt.sh, DNS, Wayback)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import domain_recon as dr  # noqa: E402

from .base import EnricherResult, enricher  # noqa: E402


@enricher("domain_recon", "domain")
def enrich_domain(value: str) -> EnricherResult:
    res = EnricherResult("domain_recon", "domain", value)
    root = res.node("domain", value)

    reg = dr.rdap(value)
    if isinstance(reg, dict) and not reg.get("error"):
        root.attrs.update({k: reg.get(k) for k in ("registered", "expires", "status")})
        res.fact(f"Зарегистрирован {reg.get('registered')}, истекает {reg.get('expires')}",
                 "rdap.org", "B2")
        for ns in (reg.get("nameservers") or []):
            n = res.node("domain", ns, role="nameserver")
            res.edge(root, n, "uses_ns")

    dns = dr.dns_records(value)
    for ip in (dns.get("A", []) + dns.get("AAAA", [])):
        n = res.node("ip", ip)
        res.edge(root, n, "resolves_to")
    for mx in dns.get("MX", []):
        res.fact(f"MX: {mx}", "DNS")
    for txt in dns.get("TXT", []):
        if "spf" in txt.lower() or "dmarc" in txt.lower():
            res.fact(f"Mail policy: {txt}", "DNS")

    subs = dr.crtsh(value)
    if isinstance(subs, list):
        res.fact(f"Поддоменов в crt.sh: {len(subs)}", "crt.sh", "B2")
        for s in subs:
            if s != value and s.endswith("." + value) and "@" not in s and " " not in s:
                n = res.node("domain", s, role="subdomain")
                res.edge(n, root, "subdomain_of")

    wb = dr.wayback(value)
    if isinstance(wb, dict) and wb.get("url"):
        root.attrs["wayback"] = wb.get("url")
        res.fact(f"Архив Wayback: {wb.get('timestamp')}", "web.archive.org")

    return res
