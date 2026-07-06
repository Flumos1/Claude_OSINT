"""
Энричер репутации IP — GreyNoise Community API (keyless, rate-limited).

Показывает, «шумит» ли IP в интернете (сканеры/боты) и относится ли к доверенной
инфраструктуре (RIOT). classification: benign / malicious / unknown.
"""
import requests

from .base import EnricherResult, enricher

TIMEOUT = 15
UA = {"User-Agent": "osint-ip-rep/1.0"}


@enricher("ip_reputation", "ip")
def enrich_ip_reputation(value: str) -> EnricherResult:
    res = EnricherResult("ip_reputation", "ip", value)
    root = res.node("ip", value)
    try:
        r = requests.get(f"https://api.greynoise.io/v3/community/{value}", headers=UA, timeout=TIMEOUT)
        if r.status_code == 404:
            res.fact("GreyNoise: IP не наблюдался (нет массовой шумовой активности).", "greynoise.io")
            return res
        if r.status_code == 429:
            res.fact("GreyNoise: превышен лимит community API — повтори позже.", "greynoise.io")
            return res
        d = r.json()
        cls = d.get("classification", "unknown")
        noise = d.get("noise")
        riot = d.get("riot")
        name = d.get("name", "")
        extra = f", {name}" if name and name.lower() != "unknown" else ""
        res.fact(f"GreyNoise: classification={cls}, noise={noise}, riot={riot}{extra}",
                 "greynoise.io community", "C3")
        root.attrs.update({"gn_classification": cls, "gn_noise": noise, "gn_riot": riot})
        if cls == "malicious":
            res.fact("⚠ GreyNoise помечает IP как malicious — проверь в контексте инцидента.",
                     "greynoise.io community", "C3")
    except Exception as e:
        res.error = str(e)
    return res
