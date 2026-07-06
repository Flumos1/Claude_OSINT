"""
Энричер ip.ports — открытые порты/уязвимости/hostnames через Shodan InternetDB.

internetdb.shodan.io — БЕСПЛАТНЫЙ, БЕЗ КЛЮЧА (лёгкая версия Shodan): по IP отдаёт открытые
порты, CPE, CVE, hostnames, теги. Пассивно (данные из сканов Shodan, мы сами не сканируем —
это законно и не оставляет следа у объекта). Пивотит на ip_geo_asn (тот же узел IP).
"""
import requests

from .base import EnricherResult, enricher

TIMEOUT = 15


@enricher("ip_ports", "ip")
def enrich_ip_ports(value: str) -> EnricherResult:
    res = EnricherResult("ip_ports", "ip", value)
    ip = value.strip()
    root = res.node("ip", ip)
    try:
        r = requests.get(f"https://internetdb.shodan.io/{ip}",
                         headers={"User-Agent": "osint-ipports/1.0"}, timeout=TIMEOUT)
        if r.status_code == 404:
            res.fact("InternetDB: даних немає (IP не у сканах Shodan)", "internetdb.shodan.io")
            return res
        if r.status_code != 200:
            res.error = f"HTTP {r.status_code} (internetdb)"
            return res
        d = r.json()
        ports = d.get("ports") or []
        cves = d.get("vulns") or []
        hostnames = d.get("hostnames") or []
        tags = d.get("tags") or []
        root.attrs.update({"open_ports": ",".join(map(str, ports)) or None,
                           "cve_count": len(cves) or None})
        if ports:
            res.fact(f"Відкриті порти ({len(ports)}): {', '.join(map(str, ports))}",
                     "internetdb.shodan.io", "B2")
        if cves:
            shown = ", ".join(sorted(cves)[:12])
            res.fact(f"Уразливості CVE ({len(cves)}): {shown}{'…' if len(cves) > 12 else ''} "
                     "— перевір, чи стосуються реальних сервісів", "internetdb.shodan.io", "C3")
        for h in hostnames:
            hn = res.node("domain", h, role="ptr_hostname")
            res.edge(root, hn, "hostname_of")
            res.fact(f"Hostname: {h}", "internetdb.shodan.io", "B3")
        if tags:
            res.fact(f"Теги Shodan: {', '.join(tags)}", "internetdb.shodan.io", "C3")
        if not (ports or cves or hostnames):
            res.fact("InternetDB: запис порожній (немає портів/CVE/hostnames)", "internetdb.shodan.io")
    except Exception as e:
        res.error = str(e)
    return res
