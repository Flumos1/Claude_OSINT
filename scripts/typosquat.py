#!/usr/bin/env python3
"""
typosquat.py — генератор типосквоттинг-вариантов домена (по мотивам dnstwist).

Зачем: защита бренда и мониторинг фишинга. По одному «своему» домену генерирует
правдоподобные опечатки и похожие имена, которые злоумышленник может зарегистрировать
для фишинга/тайпсквоттинга. Опционально проверяет, какие из вариантов уже резолвятся
(значит — зарегистрированы): это кандидаты на расследование/жалобу/блокировку.

Особое внимание — IDN-омоглифы (кириллические двойники латиницы: а, е, о, с, р, х…):
классическая атака homograph для UA/RU-аудитории (домен выглядит как ваш, но это другие
символы). Такие варианты выдаются и в виде punycode (xn--…) — как их видит DNS.

Только генерация + (опционально) DNS-резолв. Сам домен-объект прямого трафика не получает,
кроме DNS-запроса при --resolve. Легально, пассивно. См. knowledge/opsec.md, ethics-legal.md.

CLI:
    python typosquat.py example.com                      # только сгенерировать список
    python typosquat.py example.com --resolve            # + проверить, какие резолвятся
    python typosquat.py example.com --resolve --max 300 --json out.json
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

# Раскладка QWERTY: соседние клавиши (для опечаток замены/вставки).
KEYBOARD = {
    "q": "was", "w": "qeasd", "e": "wrsdf", "r": "etdfg", "t": "ryfgh",
    "y": "tughj", "u": "yihjk", "i": "uojkl", "o": "ipkl", "p": "ol",
    "a": "qwsz", "s": "qweadzx", "d": "wersfcx", "f": "ertdgvc", "g": "rtyfhbv",
    "h": "tyugjnb", "j": "yuihknm", "k": "uiojlm", "l": "opk",
    "z": "asx", "x": "zsdc", "c": "xdfv", "v": "cfgb", "b": "vghn",
    "n": "bhjm", "m": "njk",
    "1": "2", "2": "13", "3": "24", "4": "35", "5": "46",
    "6": "57", "7": "68", "8": "79", "9": "80", "0": "9",
}

# ASCII-омоглифы: символ → визуально похожие замены (в т.ч. многосимвольные rn≈m, vv≈w).
ASCII_HOMO = {
    "o": ["0"], "0": ["o"], "l": ["1", "i"], "i": ["1", "l", "j"], "1": ["l", "i"],
    "e": ["3"], "3": ["e"], "a": ["4"], "4": ["a"], "s": ["5"], "5": ["s"],
    "b": ["8"], "8": ["b"], "g": ["9"], "9": ["g"], "t": ["7"], "7": ["t"],
    "z": ["2"], "2": ["z"], "m": ["rn", "nn"], "w": ["vv"], "d": ["cl"],
    "n": ["m"], "u": ["v"], "v": ["u"], "q": ["g"], "rn": ["m"],
}

# Кириллические двойники латиницы (IDN homograph). Только уверенные совпадения.
CYR_HOMO = {
    "a": "а", "c": "с", "e": "е", "o": "о", "p": "р", "x": "х", "y": "у",
    "i": "і", "s": "ѕ", "j": "ј", "h": "һ", "k": "к", "m": "м", "t": "т",
    "b": "ь", "n": "п",
}

# Подмена TLD: куда чаще всего «уезжает» тайпсквоттинг (+ украинские зоны).
TLDS = [
    "com", "net", "org", "info", "biz", "co", "io", "online", "site", "shop",
    "app", "live", "vip", "top", "xyz", "club", "store",
    "ua", "com.ua", "net.ua", "org.ua", "in.ua", "kiev.ua",
    "ru", "su", "pl", "de", "eu", "us",
]

# Слова, которые подклеивают к фишинговым доменам.
WORDS = [
    "secure", "login", "account", "verify", "support", "update", "auth",
    "official", "portal", "online", "app", "mail", "pay", "help", "service",
]

# Известные двухуровневые публичные суффиксы (для корректного выделения SLD).
MULTI_SUFFIX = {
    "com.ua", "net.ua", "org.ua", "in.ua", "co.ua", "pp.ua", "kiev.ua",
    "lviv.ua", "dp.ua", "kh.ua", "od.ua",
    "co.uk", "org.uk", "gov.uk", "ac.uk",
    "com.ru", "net.ru", "org.ru",
    "com.pl", "net.pl", "org.pl",
    "co.il", "com.tr", "com.de", "com.br", "com.au", "co.jp", "com.cn",
}


def _split(domain: str) -> tuple[str, str, str]:
    """Разбить домен на (prefix, sld, suffix). sld — то, что фаззим.

    example.com         -> ("", "example", ".com")
    sub.example.com.ua  -> ("sub.", "example", ".com.ua")
    """
    labels = domain.split(".")
    if len(labels) >= 3 and ".".join(labels[-2:]) in MULTI_SUFFIX:
        suffix = "." + ".".join(labels[-2:])
        rest = labels[:-2]
    elif len(labels) >= 2:
        suffix = "." + labels[-1]
        rest = labels[:-1]
    else:
        return "", domain, ""
    sld = rest[-1]
    prefix = ".".join(rest[:-1])
    return (prefix + "." if prefix else ""), sld, suffix


def _punycode(host: str) -> str | None:
    """ASCII/punycode-форма хоста (как его видит DNS). None — если кодировать нельзя."""
    try:
        return ".".join(
            lbl if lbl.isascii() else lbl.encode("idna").decode("ascii")
            for lbl in host.split(".")
        )
    except Exception:
        return None


# --- фаззеры (каждый возвращает список новых SLD из исходного) ---

def _omission(s: str) -> list[str]:
    return [s[:i] + s[i + 1:] for i in range(len(s))]


def _transposition(s: str) -> list[str]:
    return [s[:i] + s[i + 1] + s[i] + s[i + 2:] for i in range(len(s) - 1)]


def _repetition(s: str) -> list[str]:
    return [s[:i] + c + s[i:] for i, c in enumerate(s)]


def _keyboard_replace(s: str) -> list[str]:
    out = []
    for i, ch in enumerate(s):
        for r in KEYBOARD.get(ch, ""):
            out.append(s[:i] + r + s[i + 1:])
    return out


def _keyboard_insert(s: str) -> list[str]:
    out = []
    for i, ch in enumerate(s):
        for r in KEYBOARD.get(ch, ""):
            out.append(s[:i + 1] + r + s[i + 1:])
    return out


def _ascii_homoglyph(s: str) -> list[str]:
    out = []
    for i, ch in enumerate(s):
        for r in ASCII_HOMO.get(ch, []):
            out.append(s[:i] + r + s[i + 1:])
    return out


def _cyr_homoglyph(s: str) -> list[str]:
    """По одной кириллической подмене на вариант (реалистично и короткий punycode)."""
    out = []
    for i, ch in enumerate(s):
        tw = CYR_HOMO.get(ch)
        if tw:
            out.append(s[:i] + tw + s[i + 1:])
    return out


def _vowel_swap(s: str) -> list[str]:
    vowels = "aeiou"
    out = []
    for i, ch in enumerate(s):
        if ch in vowels:
            out += [s[:i] + v + s[i + 1:] for v in vowels if v != ch]
    return out


def _hyphenation(s: str) -> list[str]:
    return [s[:i] + "-" + s[i:] for i in range(1, len(s))]


def _addition(s: str) -> list[str]:
    return [s + c for c in "abcdefghijklmnopqrstuvwxyz0123456789"]


def _bitsquatting(s: str) -> list[str]:
    out = []
    for i, ch in enumerate(s):
        o = ord(ch)
        for b in range(8):
            c = chr(o ^ (1 << b))
            if c.isascii() and (c.isalnum() or c == "-"):
                out.append(s[:i] + c + s[i + 1:])
    return out


def _subdomain(s: str) -> list[str]:
    return [s[:i] + "." + s[i:] for i in range(1, len(s))
            if s[i - 1] != "-" and s[i] != "-"]


def generate(domain: str) -> list[dict]:
    """Список вариантов: {variant, algo, idn, punycode}. Порядок — по убыванию сигнала."""
    domain = domain.strip().lower().rstrip(".")
    prefix, sld, suffix = _split(domain)

    seen: set[str] = set()
    out: list[dict] = []

    def add(algo: str, new_sld: str, new_suffix: str | None = None) -> None:
        suf = new_suffix if new_suffix is not None else suffix
        full = prefix + new_sld + suf
        if not new_sld or full == domain or full in seen:
            return
        seen.add(full)
        idn = not full.isascii()
        out.append({
            "variant": full,
            "algo": algo,
            "idn": idn,
            "punycode": (_punycode(full) if idn else full),
        })

    def add_all(algo: str, slds: list[str]) -> None:
        for ns in slds:
            add(algo, ns)

    # высокий сигнал — что чаще всего регистрируют под тайпсквоттинг/фишинг
    add_all("omission", _omission(sld))
    add_all("transposition", _transposition(sld))
    add_all("replacement", _keyboard_replace(sld))
    add_all("homoglyph", _ascii_homoglyph(sld))
    add_all("idn-homoglyph", _cyr_homoglyph(sld))
    cur = suffix.lstrip(".")
    for tld in TLDS:
        if tld != cur:
            add("tld-swap", sld, "." + tld)
    for w in WORDS:
        add("addition-word", sld + "-" + w)
        add("addition-word", w + "-" + sld)
    # средний/низкий сигнал, но объёмный — проверяется при достаточном --max
    add_all("repetition", _repetition(sld))
    add_all("vowel-swap", _vowel_swap(sld))
    add_all("hyphenation", _hyphenation(sld))
    add_all("insertion", _keyboard_insert(sld))
    add_all("addition", _addition(sld))
    add_all("bitsquatting", _bitsquatting(sld))
    add_all("subdomain", _subdomain(sld))
    return out


def resolve(host_ascii: str) -> dict:
    """Резолвится ли домен (A/AAAA). Резолв = домен зарегистрирован и опубликован в DNS."""
    try:
        infos = socket.getaddrinfo(host_ascii, None)
        ips = sorted({i[4][0] for i in infos})
        return {"resolves": True, "ips": ips}
    except Exception:
        return {"resolves": False, "ips": []}


def check_live(variants: list[dict], limit: int, workers: int = 25) -> list[dict]:
    """Параллельно проверить, какие из первых `limit` вариантов резолвятся."""
    batch = variants[:limit]
    live: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(resolve, v["punycode"] or v["variant"]): v for v in batch}
        for fut in as_completed(futs):
            v = futs[fut]
            r = fut.result()
            if r["resolves"]:
                live.append({**v, **r})
    live.sort(key=lambda x: x["variant"])
    return live


def main() -> None:
    ap = argparse.ArgumentParser(description="Генератор типосквоттинг-вариантов домена (dnstwist-стиль)")
    ap.add_argument("domain")
    ap.add_argument("--resolve", action="store_true", help="проверить, какие варианты резолвятся (DNS)")
    ap.add_argument("--max", type=int, default=200, help="сколько вариантов резолвить (по умолчанию 200)")
    ap.add_argument("--json", metavar="FILE", help="сохранить результат в JSON")
    args = ap.parse_args()

    domain = args.domain.strip().lower()
    variants = generate(domain)
    idn = [v for v in variants if v["idn"]]

    print(f"\n=== Типосквоттинг: {domain} ===")
    print(f"Сгенерировано вариантов: {len(variants)}  (из них IDN-омоглифов: {len(idn)})")

    by_algo: dict[str, int] = {}
    for v in variants:
        by_algo[v["algo"]] = by_algo.get(v["algo"], 0) + 1
    print("По алгоритмам: " + ", ".join(f"{a}={n}" for a, n in by_algo.items()))

    if idn:
        print("\n[IDN-омоглифы — homograph, высокий риск фишинга]")
        for v in idn[:20]:
            print(f"  {v['variant']}  →  {v['punycode']}")
        if len(idn) > 20:
            print(f"  … и ещё {len(idn) - 20}")

    live: list[dict] = []
    if args.resolve:
        print(f"\n[DNS] проверяю первые {min(args.max, len(variants))} вариантов…")
        live = check_live(variants, args.max)
        if live:
            print(f"Резолвятся (зарегистрированы): {len(live)}  ⚠ кандидаты на тайпсквоттинг/фишинг")
            for v in live:
                mark = " [IDN]" if v["idn"] else ""
                puny = f"  ({v['punycode']})" if v["idn"] else ""
                print(f"  ⚠ {v['variant']}{mark}{puny}  →  {', '.join(v['ips'])}  [{v['algo']}]")
        else:
            print("Ни один из проверенных вариантов не резолвится.")

    if args.json:
        payload = {
            "domain": domain,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "generated": len(variants),
            "idn_count": len(idn),
            "variants": variants,
            "resolved_live": live if args.resolve else None,
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"\nСохранено: {args.json}")


if __name__ == "__main__":
    main()
