"""Энричер IP — гео и ASN через keyless ip-api.com (без ключа, лимит ~45 req/min)."""
import requests

from .base import EnricherResult, enricher

TIMEOUT = 15


@enricher("ip_geo_asn", "ip")
def enrich_ip(value: str) -> EnricherResult:
    res = EnricherResult("ip_geo_asn", "ip", value)
    root = res.node("ip", value)
    try:
        r = requests.get(
            f"http://ip-api.com/json/{value}",
            params={"fields": "status,message,country,regionName,city,isp,org,as,reverse,query"},
            headers={"User-Agent": "osint-ip-enricher/1.0"},
            timeout=TIMEOUT,
        )
        d = r.json()
        if d.get("status") != "success":
            res.error = d.get("message", "lookup failed")
            return res
        root.attrs.update({
            "country": d.get("country"), "city": d.get("city"),
            "isp": d.get("isp"), "org": d.get("org"), "asn": d.get("as"),
            "reverse": d.get("reverse"),
        })
        res.fact(f"Гео: {d.get('city')}, {d.get('country')}", "ip-api.com", "C3")
        res.fact(f"ASN/ISP: {d.get('as')} / {d.get('isp')}", "ip-api.com", "C3")
        if d.get("reverse"):
            n = res.node("domain", d["reverse"], role="ptr")
            res.edge(root, n, "reverse_dns")
    except Exception as e:
        res.error = str(e)
    return res
