"""
Email-MX энричер (keyless) — принимает ли домен почту (MX), настроены ли SPF/DMARC,
не одноразовый ли это адрес. Косвенная проверка «живости»/легитимности адреса по DNS.
"""
import dns.resolver

from .base import EnricherResult, enricher

_resolver = dns.resolver.Resolver()
_resolver.lifetime = 5.0
_resolver.timeout = 5.0

_DISPOSABLE = {
    "mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com",
    "yopmail.com", "trashmail.com", "getnada.com", "temp-mail.org",
    "sharklasers.com", "maildrop.cc", "dispostable.com", "fakeinbox.com",
}


def _txt(name: str) -> list[str]:
    try:
        out = []
        for r in _resolver.resolve(name, "TXT"):
            out.append(b"".join(r.strings).decode(errors="ignore"))
        return out
    except Exception:
        return []


@enricher("email_mx", "email")
def enrich_email_mx(value: str) -> EnricherResult:
    res = EnricherResult("email_mx", "email", value)
    email = value.strip().lower()
    root = res.node("email", email)
    if "@" not in email:
        res.error = "не похоже на email"
        return res
    domain = email.split("@")[1]

    try:
        mx = sorted((r.preference, str(r.exchange).rstrip(".")) for r in _resolver.resolve(domain, "MX"))
        if mx:
            res.fact(f"MX ({len(mx)}): {', '.join(m for _, m in mx[:4])} — домен принимает почту.",
                     "DNS", "C3")
            for _, m in mx[:4]:
                n = res.node("domain", m, role="mx")
                res.edge(root, n, "mail_via")
        else:
            res.fact("MX-записей нет — домен вряд ли принимает почту.", "DNS")
    except Exception:
        res.fact("MX-записи не получены (нет записи или ошибка DNS).", "DNS")

    spf = any("v=spf1" in t.lower() for t in _txt(domain))
    dmarc = any("v=dmarc1" in t.lower() for t in _txt(f"_dmarc.{domain}"))
    res.fact(f"Почтовые политики: SPF {'есть' if spf else 'нет'}, "
             f"DMARC {'есть' if dmarc else 'нет'}.", "DNS")

    if domain in _DISPOSABLE:
        root.attrs["disposable"] = True
        res.fact("⚠ Домен одноразовой/временной почты — низкое доверие к адресу.", "email_mx", "C3")
    return res
