"""
IOC-энричер — репутация индикатора (IP / домен / URL) по VirusTotal и AbuseIPDB.

Key-gated, но graceful: без ключей не падает, а подсказывает какой ключ добавить.
- VIRUSTOTAL_API_KEY (free): vt-вердикт по IP/домену/URL.
- ABUSEIPDB_API_KEY (free, только IP): confidence score, число жалоб.
GreyNoise (шум/RIOT) — отдельный keyless энричер ip_reputation.
Регистрируется для ip/domain/url; тип определяется по значению.
"""
import base64
import os
import re

import requests

from .base import EnricherResult, enricher

TIMEOUT = 20
UA = {"User-Agent": "osint-ioc/1.0"}
IP_RE = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")


def _kind(v: str) -> str:
    if IP_RE.match(v):
        return "ip"
    if v.startswith("http://") or v.startswith("https://"):
        return "url"
    return "domain"


def _vt(res: EnricherResult, kind: str, v: str, key: str) -> None:
    if kind == "url":
        ident = base64.urlsafe_b64encode(v.encode()).decode().rstrip("=")
        path = f"urls/{ident}"
    elif kind == "ip":
        path = f"ip_addresses/{v}"
    else:
        path = f"domains/{v}"
    r = requests.get(f"https://www.virustotal.com/api/v3/{path}",
                     headers={"x-apikey": key, **UA}, timeout=TIMEOUT)
    if r.status_code == 404:
        res.fact("VirusTotal: индикатор не найден в базе.", "VirusTotal API", "C3")
        return
    if not r.ok:
        res.fact(f"VirusTotal: HTTP {r.status_code}.", "VirusTotal API")
        return
    stats = (((r.json().get("data") or {}).get("attributes") or {}).get("last_analysis_stats") or {})
    mal, susp = stats.get("malicious", 0), stats.get("suspicious", 0)
    res.fact(f"VirusTotal: malicious={mal}, suspicious={susp}, "
             f"harmless={stats.get('harmless', 0)} (вендоров).", "VirusTotal API",
             "B2" if (mal or susp) else "C3")
    if mal or susp:
        res.fact(f"⚠ VirusTotal: {mal + susp} движков считают индикатор вредоносным.",
                 "VirusTotal API", "B2")


def _abuseipdb(res: EnricherResult, v: str, key: str) -> None:
    r = requests.get("https://api.abuseipdb.com/api/v2/check",
                     params={"ipAddress": v, "maxAgeInDays": 90},
                     headers={"Key": key, "Accept": "application/json", **UA}, timeout=TIMEOUT)
    if not r.ok:
        res.fact(f"AbuseIPDB: HTTP {r.status_code}.", "AbuseIPDB API")
        return
    d = (r.json().get("data") or {})
    score = d.get("abuseConfidenceScore", 0)
    res.fact(f"AbuseIPDB: confidence={score}%, жалоб {d.get('totalReports', 0)}, "
             f"страна {d.get('countryCode') or '—'}, ISP {d.get('isp') or '—'}.",
             "AbuseIPDB API", "B2" if score >= 25 else "C3")


@enricher("ioc", "ip")
@enricher("ioc", "domain")
@enricher("ioc", "url")
def enrich_ioc(value: str) -> EnricherResult:
    res = EnricherResult("ioc", _kind(value), value)
    v = value.strip()
    kind = _kind(v)
    res.node(kind, v)

    vt_key = os.getenv("VIRUSTOTAL_API_KEY")
    abuse_key = os.getenv("ABUSEIPDB_API_KEY")
    if not vt_key and not abuse_key:
        res.fact("Ключей нет (VIRUSTOTAL_API_KEY / ABUSEIPDB_API_KEY) — добавь в .env "
                 "(оба бесплатны). Ручная проверка: virustotal.com, abuseipdb.com.", "config")
        return res
    try:
        if vt_key:
            _vt(res, kind, v, vt_key)
        if abuse_key and kind == "ip":
            _abuseipdb(res, v, abuse_key)
        if not vt_key:
            res.fact("VIRUSTOTAL_API_KEY не задан — VT-вердикт пропущен.", "config")
        if not abuse_key and kind == "ip":
            res.fact("ABUSEIPDB_API_KEY не задан — AbuseIPDB пропущен.", "config")
    except Exception as e:
        res.error = str(e)
    return res
