"""
Энричер IP-портов — открытые порты/сервисы/уязвимости через Shodan InternetDB.

https://internetdb.shodan.io/{ip} — БЕСПЛАТНО, без ключа (пассивные данные последнего
скана Shodan). Это не активное сканирование цели, а чтение уже опубликованного.
"""
import requests

from .base import EnricherResult, enricher

TIMEOUT = 15


@enricher("ip_ports", "ip")
def enrich_ip_ports(value: str) -> EnricherResult:
    res = EnricherResult("ip_ports", "ip", value)
    root = res.node("ip", value)
    try:
        r = requests.get(f"https://internetdb.shodan.io/{value}",
                         headers={"User-Agent": "osint-ip-ports/1.0"}, timeout=TIMEOUT)
        if r.status_code == 404:
            res.fact("InternetDB: данных по IP нет (не индексировался Shodan).", "internetdb.shodan.io")
            return res
        d = r.json()
        ports = d.get("ports", []) or []
        hostnames = d.get("hostnames", []) or []
        cpes = d.get("cpes", []) or []
        vulns = d.get("vulns", []) or []
        tags = d.get("tags", []) or []
        root.attrs.update({"open_ports": len(ports), "vulns": len(vulns)})
        if ports:
            res.fact(f"Открытые порты ({len(ports)}): {', '.join(map(str, ports))}",
                     "internetdb.shodan.io", "C3")
        for h in hostnames:
            n = res.node("domain", h, role="hostname")
            res.edge(root, n, "hosts")
        if cpes:
            res.fact(f"Технологии (CPE): {', '.join(cpes[:8])}{'…' if len(cpes) > 8 else ''}",
                     "internetdb.shodan.io", "C3")
        if tags:
            res.fact(f"Метки Shodan: {', '.join(tags)}", "internetdb.shodan.io", "C3")
        if vulns:
            res.fact(f"⚠ Известные CVE ({len(vulns)}): {', '.join(vulns[:10])}"
                     f"{'…' if len(vulns) > 10 else ''} — проверь применимость.",
                     "internetdb.shodan.io", "C3")
        if not ports and not hostnames and not vulns:
            res.fact("InternetDB: запись пустая (нет открытых портов в индексе).", "internetdb.shodan.io")
    except Exception as e:
        res.error = str(e)
    return res
