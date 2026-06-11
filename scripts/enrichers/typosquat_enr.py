"""Энричер typosquat — генерирует типо-варианты домена и проверяет, какие резолвятся.

Защита бренда / мониторинг фишинга (в стиле dnstwist). Резолвящиеся варианты — это
зарегистрированные домены, кандидаты на тайпсквоттинг/homograph-фишинг. Особый акцент —
IDN-омоглифы (кириллические двойники латиницы), классическая атака для UA/RU-аудитории.

Энричер делает DNS-запросы по сгенерированным вариантам (до MAX_RESOLVE), поэтому он
активнее пассивных источников; объект-оригинал прямого трафика не получает. Полный
исчерпывающий прогон — отдельной утилитой: python typosquat.py <домен> --resolve --max N
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import typosquat as ts  # noqa: E402

from .base import EnricherResult, enricher  # noqa: E402

MAX_RESOLVE = 150  # сколько вариантов резолвить в рамках энричера (CLI — без лимита)


@enricher("typosquat", "domain")
def enrich_typosquat(value: str) -> EnricherResult:
    res = EnricherResult("typosquat", "domain", value)
    root = res.node("domain", value)

    variants = ts.generate(value)
    res.fact(f"Сгенерировано {len(variants)} типо-вариантов (dnstwist-стиль)", "typosquat")

    idn = [v for v in variants if v["idn"]]
    if idn:
        res.fact(
            f"IDN-омоглифов (homograph, кириллица): {len(idn)} — высокий риск фишинга",
            "typosquat", "C2",
        )

    checked = min(MAX_RESOLVE, len(variants))
    live = ts.check_live(variants, MAX_RESOLVE)
    if live:
        res.fact(
            f"Резолвятся {len(live)} из проверенных {checked} вариантов — "
            f"кандидаты на тайпсквоттинг/фишинг",
            "DNS", "B2",
        )
    else:
        res.fact(f"Из проверенных {checked} вариантов ни один не резолвится", "DNS", "C3")

    for v in live:
        n = res.node(
            "domain", v["variant"], role="typosquat", algo=v["algo"],
            idn=v["idn"], punycode=v["punycode"], ips=", ".join(v["ips"]),
        )
        res.edge(n, root, "typosquat_of")
        tag = "IDN-homograph" if v["idn"] else v["algo"]
        puny = f" (punycode {v['punycode']})" if v["idn"] else ""
        res.fact(f"⚠ {v['variant']}{puny} → {', '.join(v['ips'])} [{tag}]", "DNS", "B2")

    return res
