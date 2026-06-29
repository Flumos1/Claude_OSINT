"""
Энричер тайпсквоттинга — генерирует look-alike варианты домена и проверяет,
какие из них РЕАЛЬНО зарегистрированы (резолвятся). Зарегистрированные двойники —
кандидаты на фишинг/бренд-сквоттинг. Keyless (DNS через dnspython).

Лёгкий аналог dnstwist: omission/transposition/repetition/homoglyph + подмена TLD.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed

import dns.resolver

from .base import EnricherResult, enricher

_TLDS = ("com", "net", "org", "co", "io", "app", "xyz", "online", "site",
         "ru", "ua", "info", "top", "shop")
_HOMOGLYPH = {"o": "0", "l": "1", "i": "1", "e": "3", "s": "5", "b": "6", "g": "9", "a": "4"}
MAX_VARIANTS = 80
WORKERS = 20

_resolver = dns.resolver.Resolver()
_resolver.lifetime = 3.0
_resolver.timeout = 3.0


def _variants(domain: str) -> list[str]:
    parts = domain.lower().strip().strip(".").split(".")
    if len(parts) < 2:
        return []
    base, tld = parts[-2], parts[-1]
    prefix = ".".join(parts[:-2])

    def dom(b: str, t: str) -> str:
        labels = ([prefix] if prefix else []) + [b, t]
        return ".".join(labels)

    out: set[str] = set()
    for i in range(len(base)):
        out.add(dom(base[:i] + base[i + 1:], tld))            # пропуск буквы
        out.add(dom(base[:i] + base[i] + base[i:], tld))      # удвоение
    for i in range(len(base) - 1):
        lst = list(base)
        lst[i], lst[i + 1] = lst[i + 1], lst[i]
        out.add(dom("".join(lst), tld))                       # перестановка
    for i, ch in enumerate(base):
        if ch in _HOMOGLYPH:
            out.add(dom(base[:i] + _HOMOGLYPH[ch] + base[i + 1:], tld))  # гомоглиф
    for t in _TLDS:
        if t != tld:
            out.add(dom(base, t))                             # подмена TLD
    out.discard(domain.lower())
    out = {v for v in out if v and len(v.split(".")[-2]) > 0}
    return sorted(out)[:MAX_VARIANTS]


def _resolves(d: str):
    try:
        return [r.address for r in _resolver.resolve(d, "A")]
    except Exception:
        return None


@enricher("typosquat", "domain")
def enrich_typosquat(value: str) -> EnricherResult:
    res = EnricherResult("typosquat", "domain", value)
    root = res.node("domain", value)
    variants = _variants(value)
    if not variants:
        res.error = "не удалось разобрать домен"
        return res

    registered = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(_resolves, v): v for v in variants}
        for fut in as_completed(futs):
            ips = fut.result()
            if ips:
                registered.append((futs[fut], ips))

    registered.sort()
    for dom, ips in registered:
        n = res.node("domain", dom, role="typosquat", resolves_to=", ".join(ips[:3]))
        res.edge(root, n, "typosquat_of")
        res.fact(f"⚠ Зарегистрированный двойник: {dom} → {', '.join(ips[:3])}", "DNS", "C3")

    res.fact(f"Проверено вариантов: {len(variants)}; зарегистрировано двойников: "
             f"{len(registered)}. Зарегистрированные — кандидаты на фишинг/сквоттинг, "
             f"проверь вручную (контент, сертификат, владелец).", "typosquat")
    return res
