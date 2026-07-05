#!/usr/bin/env python3
"""
person_search.py — интеллектуальный поиск физлица по открытым легальным источникам.

Принимает ФИО (+ опц. дату рождения, РНОКПП/ИНН, известные email/телефон/username) и
делает фан-аут по реестрам UA/RU/международным: генерирует варианты написания имени,
валидирует идентификатор, делает ЖИВЫЕ запросы туда, где есть открытое API без ключа
(НАЗК), пивотит предоставленные селекторы (email/username), и формирует точные deep-ссылки
на остальные реестры. Итог — досье (граф + факты + сгруппированные ссылки + правовые оговорки).

⚖️ ГРАНИЦЫ (жёстко): только открытые/законные источники. НЕ используем сервисы «пробива»,
слитые базы, серые боты. Паспортные данные закрыты. Недвижимость по ФИО (ДРРП/Росреестр) —
через э-идентификацию/платно, не открыто. Поиск частного лица — только при правовом основании
(зафиксируй его). Тул агрегирует уже опубликованное и пивотит предоставленные данные.

CLI:
    python person_search.py "Прізвище Ім'я По-батькові" --countries ua,ru,intl
    python person_search.py "Иванов Иван" --dob 1980-01-01 --rnokpp 1234567890 \
        --email a@b.com --username ivan --json ..\\cases\\<slug>\\data\\person.json
"""
import argparse
import json
import sys
from urllib.parse import quote

import os

from translit import name_variants
from sanctions import check_opensanctions
from dorks import person_dorks
from enrichers.ua_person_enr import valid_rnokpp
from enrichers.ru_company_enr import valid_inn
from enrichers.nazk_enr import enrich_nazk
from enrichers.email_enr import enrich_email
from enrichers.email_leaks_enr import enrich_email_leaks
from enrichers.username_enr import enrich_username
from enrichers.phone_enr import enrich_phone

BASIS = ("⚖️ Поиск физлица допустим только при правовом основании (KYC/DD/расследование/"
         "взыскание). Зафиксируй основание в кейсе. Только открытые источники; «пробив»/"
         "слитые базы/паспорт/недвижимость-по-ФИО — вне закона/недоступны.")

LEGAL_NOTES = [
    "Паспортные данные — закрыты. Открыто только: проверка НЕдействительности номера паспорта "
    "(МВС UA wanted.mvs.gov.ua/passport) — не раскрывает чужой паспорт.",
    "Недвижимость по ФИО: UA ДРРП — через Дія (э-идентификация); RU Росреестр — платно/ограничено. "
    "Открытый кадастр ищется по участку, а не по человеку.",
    "Телефон/email/адрес частного лица — только там, где он легально опубликован (ФОП-реєстр, "
    "объявления, соцсети, декларації). «Пробив» по слитым базам не используется.",
]


def ua_registries(name, rnokpp):
    q = quote(name)
    L = [
        ("Єдиний реєстр судових рішень", f"https://reyestr.court.gov.ua/?suchau={q}", "суды: полные тексты"),
        ("Декларації НАЗК", f"https://public.nazk.gov.ua/documents/list?q={q}", "декларації посадовців"),
        ("PEP (публічні діячі)", f"https://pep.org.ua/uk/search?q={q}", "PEP та пов'язані"),
        ("Реєстр корупціонерів (НАЗК)", "https://corruptinfo.nazk.gov.ua/", "корупційні правопорушення (пошук за ПІБ)"),
        ("Люстрація (Очищення влади)", "https://lustration.minjust.gov.ua/register", "заборона обіймати посади"),
        ("ЄДЕБО (документи про освіту)", "https://info.edbo.gov.ua/edu-documents", "верифікація диплома"),
        ("Єдиний реєстр боржників", "https://erb.minjust.gov.ua/", "борги (пошук за ПІБ)"),
        ("АСВП (виконавчі провадж.)", "https://asvpweb.minjust.gov.ua/", "виконавчі (ПІБ/ІПН)"),
        ("Держреєстр санкцій (РНБО)", "https://drs.nsdc.gov.ua/", "санкції"),
        ("Розшук осіб (МВС)", "https://wanted.mvs.gov.ua/searchperson/", "розшук"),
        ("Втрачені паспорти (МВС)", "https://wanted.mvs.gov.ua/passport/", "недійсні паспорти"),
        ("ФОП-пошук (Opendatabot)", "https://opendatabot.ua/open/fop-search", "якщо підприємець: адреса/КВЕД"),
        ("YouControl (фізособи)", f"https://youcontrol.com.ua/search/?q={q}", "зв'язки/реєстри (free 22)"),
    ]
    return [{"name": n, "url": u, "note": d} for n, u, d in L]


def ru_registries(name, dob, inn):
    q = quote(name)
    L = [
        ("ФССП (исп. производства)", "https://fssp.gov.ru/iss/ip", "долги (нужны ФИО+дата рожд.)"),
        ("Банкротство (Федресурс)", f"https://bankrot.fedresurs.ru/bankrupts?searchString={q}", "банкротство физлиц"),
        ("Суды (ГАС Правосудие)", "https://bsr.sudrf.ru/bigs/portal.html", "судебные акты по ФИО"),
        ("Прозрачный бизнес (ФНС)", "https://pb.nalog.ru/", "дисквалификация / ИП"),
        ("ЕГРИП (если ИП)", "https://egrul.nalog.ru/", "ИП по ФИО/ИНН"),
        ("Розыск МВД", "https://мвд.рф/wanted", "розыск"),
    ]
    return [{"name": n, "url": u, "note": d} for n, u, d in L]


def intl_registries(name, email):
    q = quote(name)
    L = [
        ("OpenSanctions", f"https://www.opensanctions.org/search/?q={q}", "санкции/PEP (агрегатор)"),
        ("OFAC SDN (США)", "https://sanctionssearch.ofac.treas.gov/", "санкции США"),
        ("ICIJ Offshore Leaks", f"https://offshoreleaks.icij.org/search?q={q}", "офшоры/бенефициары"),
        ("OCCRP Aleph", f"https://aleph.occrp.org/search?q={q}", "документы/реестры/утечки"),
        ("LittleSis", f"https://littlesis.org/search?q={q}", "связи людей/корпораций"),
    ]
    if email:
        L.append(("HIBP (email в утечках)", f"https://haveibeenpwned.com/unifiedsearch/{quote(email)}",
                  "факт компрометации (нужен ключ для API)"))
    return [{"name": n, "url": u, "note": d} for n, u, d in L]


def search_person(name, dob=None, rnokpp=None, email=None, phone=None, username=None,
                  countries=("ua", "ru", "intl")):
    variants = name_variants(name)
    nodes, edges, findings = {}, [], []

    def node(t, v, **a):
        key = f"{t}:{v.strip().lower()}"
        nodes.setdefault(key, {"id": key, "type": t, "value": v, "attrs": a})
        return key

    def fact(text, src, conf=""):
        findings.append({"label": "FACT", "text": text, "source": src, "confidence": conf})

    root = node("person", name, dob=dob or "", rnokpp=rnokpp or "")
    fact(f"Варианты написания (для полноты поиска): {', '.join(variants)}", "translit")

    # Идентификатор
    id_check = {}
    if rnokpp:
        if valid_rnokpp(rnokpp):
            id_check = {"type": "РНОКПП", "valid": True}
            fact(f"РНОКПП {rnokpp}: валиден (контр. сумма).", "checksum", "A1")
        elif len(rnokpp) == 12 and valid_inn(rnokpp):
            id_check = {"type": "ИНН-RU (физлицо)", "valid": True}
            fact(f"ИНН {rnokpp}: валиден (12-знач., физлицо РФ).", "checksum", "A1")
        else:
            id_check = {"type": "id", "valid": False}
            fact(f"Идентификатор {rnokpp}: контр. сумма НЕ сошлась — проверь опечатку.", "checksum")
        fact("⚠️ Идентификатор — персональные данные; обрабатывай по основанию.", "ethics-legal")
    if dob:
        fact(f"Дата рождения {dob} — ключ дизамбигуации (ФССП/суды требуют для точности).", "методология")

    # ЖИВЫЕ источники
    registries = {}
    if "ua" in countries:
        registries["ua"] = ua_registries(name, rnokpp)
        # НАЗК — живой запрос по основному имени и русифицированному варианту
        seen = 0
        for nm in dict.fromkeys([name] + variants[:2]):
            if nm.replace(" ", "").isdigit():
                continue
            res = enrich_nazk(nm)
            for f in res.findings:
                if "Декларацій НАЗК" in f.text or "декларація" in f.text:
                    findings.append({"label": "FACT", "text": f"[НАЗК «{nm}»] {f.text}",
                                     "source": f.source, "confidence": f.confidence})
                    seen += 1
            if seen >= 12:
                break
    if "ru" in countries:
        registries["ru"] = ru_registries(name, dob, rnokpp)
        fact("RU-реестры (ФССП/Федресурс/суды) под капчей/бот-защитой — живой запрос требует "
             "токена (FSSP_API_KEY) или ручной проверки по ссылкам; для ФССП нужны ФИО+дата рождения.",
             "методология")
    if "intl" in countries:
        registries["intl"] = intl_registries(name, email)

    # Пивот предоставленных селекторов
    selectors = {}
    if email:
        node("email", email); edges.append({"source": root, "target": f"email:{email.lower()}", "rel": "has_email"})
        er = enrich_email(email)
        lr = enrich_email_leaks(email)  # HIBP (по ключу)
        selectors["email"] = [f.text for f in er.findings + lr.findings]
        for f in er.findings + lr.findings:
            fact(f"[email] {f.text}", f.source, f.confidence)
    if username:
        ur = enrich_username(username)
        selectors["username"] = [f.text for f in ur.findings if "профіль існує" in f.text]
        for n2 in ur.nodes:
            if n2.type == "url":
                k = node("url", n2.value, platform=n2.attrs.get("platform"))
                edges.append({"source": root, "target": k, "rel": "profile_on"})
        for f in ur.findings:
            fact(f"[username] {f.text}", f.source, f.confidence)
    if phone:
        node("phone", phone); edges.append({"source": root, "target": f"phone:{phone.lower()}", "rel": "has_phone"})
        pr = enrich_phone(phone)  # keyless: оператор/регион/тип через phonenumbers
        selectors["phone"] = [f.text for f in pr.findings]
        for f in pr.findings:
            fact(f"[phone] {f.text}", f.source, f.confidence)

    # Дорки для ручного поиска (резюме/соцсети/контакты/пасты)
    for dk in person_dorks(name):
        fact(f"Дорк [{dk['label']}]: {dk['url']}", "dorks")

    # Санкции/PEP — живой поиск (по ключу OpenSanctions), иначе deep-ссылка (в registries.intl)
    sanc_hits = None
    if "intl" in countries:
        sanc_hits = check_opensanctions(name)
        if sanc_hits is not None:
            fact(f"OpenSanctions (live): совпадений {len(sanc_hits)}", "OpenSanctions API", "B2")
            for h in sanc_hits[:8]:
                topics = ", ".join(h.get("topics") or []) or "—"
                fact(f"  {h['caption']} [{h['schema']}] topics={topics} score={h['score']}",
                     "OpenSanctions API", "B2")

    return {
        "query": {"name": name, "dob": dob, "rnokpp": rnokpp, "email": email,
                  "phone": phone, "username": username, "countries": list(countries)},
        "basis": BASIS,
        "name_variants": variants,
        "id_check": id_check,
        "registries": registries,
        "selectors": selectors,
        "sanctions": sanc_hits,
        "notes": LEGAL_NOTES,
        "nodes": list(nodes.values()),
        "edges": edges,
        "findings": findings,
    }


def dossier_to_markdown(d: dict) -> str:
    """Рендер досье в Markdown-отчёт (далее конвертируется в DOCX/PDF скилами)."""
    q = d["query"]
    L = [
        f"# Досье ФЛ: {q['name']}",
        "",
        "| | |", "|---|---|",
        f"| **ФИО** | {q['name']} |",
        f"| **Дата рождения** | {q.get('dob') or '—'} |",
        f"| **РНОКПП/ИНН** | {q.get('rnokpp') or '—'} |",
        f"| **Страны** | {', '.join(q.get('countries') or [])} |",
        f"| **Дата сбора** | 2026-06-10 |",
        "",
        f"> {d['basis']}",
        "",
        "## Варианты написания (для полноты поиска)",
        "",
        ", ".join(d["name_variants"]),
        "",
        "## Находки (живые источники)",
        "",
    ]
    for f in d["findings"]:
        c = f" `[{f['confidence']}]`" if f["confidence"] else ""
        L.append(f"- **{f['label']}**{c} {f['text']} — _{f['source']}_")
    for ctry, regs in d["registries"].items():
        L += ["", f"## Реестры — {ctry.upper()} (точки входа)", ""]
        for r in regs:
            L.append(f"- [{r['name']}]({r['url']}) — {r['note']}")
    L += ["", "## Правовые ограничения", ""]
    L += [f"- {n}" for n in d["notes"]]
    L += ["", "---", "> Открытые источники на дату сбора. Совпадение идентификаторов не гарантирует "
          "тождество лица. Не является юридическим заключением."]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="Интеллектуальный поиск физлица (открытые источники)")
    ap.add_argument("name", help="ФИО / ПІБ")
    ap.add_argument("--dob", help="дата рождения ГГГГ-ММ-ДД")
    ap.add_argument("--rnokpp", help="РНОКПП (UA) или ИНН-физлицо (RU, 12 цифр)")
    ap.add_argument("--email"); ap.add_argument("--phone"); ap.add_argument("--username")
    ap.add_argument("--countries", default="ua,ru,intl")
    ap.add_argument("--json", metavar="FILE")
    ap.add_argument("--report", metavar="FILE.md", help="сохранить досье как Markdown-отчёт")
    args = ap.parse_args()

    d = search_person(args.name, args.dob, args.rnokpp, args.email, args.phone,
                      args.username, tuple(c.strip() for c in args.countries.split(",") if c.strip()))
    print("\n" + BASIS + "\n")
    print(f"=== {args.name} ===  варианты: {len(d['name_variants'])}")
    print("\n[Факты]")
    for f in d["findings"]:
        c = f" [{f['confidence']}]" if f["confidence"] else ""
        print(f"  ({f['label']}{c}) {f['text']}  — {f['source']}")
    for ctry, regs in d["registries"].items():
        print(f"\n[Реестры {ctry.upper()}]")
        for r in regs:
            print(f"  {r['name']}: {r['url']}  ({r['note']})")
    print("\n[Правовые ограничения]")
    for n in d["notes"]:
        print(f"  • {n}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        print(f"\nДосье (JSON) сохранено: {args.json}")
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(dossier_to_markdown(d))
        print(f"Отчёт (Markdown) сохранён: {args.report}")


if __name__ == "__main__":
    main()
