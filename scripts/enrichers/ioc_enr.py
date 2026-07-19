"""
Энричер ioc_reputation — репутация индикатора (IP/домен/URL) через threat-intel сервисы.

Закрывает скил threat-intel. Источники (key-gated, из scripts/.env), каждый устойчив и
graceful: без ключа — deep-ссылка на веб-версию, с ключом — живой вердикт.
  • VirusTotal (v3): VIRUSTOTAL_API_KEY — ip/domain/url, движки malicious/suspicious.
  • AbuseIPDB:       ABUSEIPDB_API_KEY  — ip, confidence-score злоупотреблений.
  • GreyNoise (community): GREYNOISE_API_KEY — ip, шум/классификация сканеров.

Пассивная проверка репутации по агрегаторам — законно и без следа у объекта.
"""
import base64
import os

import requests

from .base import EnricherResult, enricher

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except Exception:
    pass

# 20с при кількох послідовних викликах (VT+AbuseIPDB+GreyNoise, ще й серед 9
# domain-енричерів загалом) — забагато на одне джерело.
TIMEOUT = 12
UA = {"User-Agent": "osint-ioc/1.0"}


def _vt(res, itype, value):
    key = os.getenv("VIRUSTOTAL_API_KEY")
    web = {"ip": f"https://www.virustotal.com/gui/ip-address/{value}",
           "domain": f"https://www.virustotal.com/gui/domain/{value}",
           "url": "https://www.virustotal.com/gui/home/url"}[itype]
    if not key:
        res.fact(f"VirusTotal (без ключа): {web}", "deep-link")
        return
    path = {"ip": f"ip_addresses/{value}", "domain": f"domains/{value}",
            "url": f"urls/{base64.urlsafe_b64encode(value.encode()).decode().strip('=')}"}[itype]
    try:
        r = requests.get(f"https://www.virustotal.com/api/v3/{path}",
                         headers={**UA, "x-apikey": key}, timeout=TIMEOUT)
        if r.status_code != 200:
            res.fact(f"VirusTotal: HTTP {r.status_code} (перевір ключ/індикатор). Веб: {web}", "config")
            return
        st = r.json().get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
        mal, susp = st.get("malicious", 0), st.get("suspicious", 0)
        conf = "F1" if (mal + susp) == 0 else ("B1" if mal >= 3 else "C2")
        res.fact(f"VirusTotal: malicious={mal}, suspicious={susp}, "
                 f"harmless={st.get('harmless', 0)}", "VirusTotal API", conf)
    except Exception as e:
        res.error = (res.error + "; " if res.error else "") + f"VT: {e}"


def _abuseipdb(res, value):
    key = os.getenv("ABUSEIPDB_API_KEY")
    web = f"https://www.abuseipdb.com/check/{value}"
    if not key:
        res.fact(f"AbuseIPDB (без ключа): {web}", "deep-link")
        return
    try:
        r = requests.get("https://api.abuseipdb.com/api/v2/check",
                         params={"ipAddress": value, "maxAgeInDays": 90},
                         headers={**UA, "Key": key, "Accept": "application/json"}, timeout=TIMEOUT)
        if r.status_code != 200:
            res.fact(f"AbuseIPDB: HTTP {r.status_code}. Веб: {web}", "config")
            return
        d = r.json().get("data", {})
        score = d.get("abuseConfidenceScore", 0)
        conf = "B1" if score >= 50 else ("C2" if score >= 10 else "D3")
        res.fact(f"AbuseIPDB: confidence={score}%, звітів={d.get('totalReports', 0)}, "
                 f"країна={d.get('countryCode', '?')}, ISP={d.get('isp', '?')}", "AbuseIPDB API", conf)
    except Exception as e:
        res.error = (res.error + "; " if res.error else "") + f"AbuseIPDB: {e}"


def _greynoise(res, value):
    key = os.getenv("GREYNOISE_API_KEY")
    web = f"https://viz.greynoise.io/ip/{value}"
    if not key:
        res.fact(f"GreyNoise (без ключа): {web}", "deep-link")
        return
    try:
        r = requests.get(f"https://api.greynoise.io/v3/community/{value}",
                         headers={**UA, "key": key}, timeout=TIMEOUT)
        if r.status_code == 404:
            res.fact("GreyNoise: IP не спостерігався (не сканер/не шум).", "GreyNoise API", "D3")
            return
        if r.status_code != 200:
            res.fact(f"GreyNoise: HTTP {r.status_code}. Веб: {web}", "config")
            return
        d = r.json()
        cls = d.get("classification", "unknown")
        conf = "B1" if cls == "malicious" else ("F1" if cls == "benign" else "C3")
        res.fact(f"GreyNoise: класифікація={cls}, noise={d.get('noise')}, "
                 f"riot={d.get('riot')}, name={d.get('name', '?')}", "GreyNoise API", conf)
    except Exception as e:
        res.error = (res.error + "; " if res.error else "") + f"GreyNoise: {e}"


def _run(itype, value):
    res = EnricherResult("ioc_reputation", itype, value)
    res.node(itype, value.strip())
    res.fact("⚖️ Пасивна перевірка репутації індикатора (threat-intel). Захисний фокус.",
             "threat-intel")
    _vt(res, itype, value.strip())
    if itype == "ip":
        _abuseipdb(res, value.strip())
        _greynoise(res, value.strip())
    return res


@enricher("ioc_reputation", "ip")
def enrich_ioc_ip(value): return _run("ip", value)


@enricher("ioc_reputation", "domain")
def enrich_ioc_domain(value): return _run("domain", value)


@enricher("ioc_reputation", "url")
def enrich_ioc_url(value): return _run("url", value)
