"""
UA-энричер физлица (приоритетная страна). По ПІБ или РНОКПП (ІПН):
валидирует контрольную сумму РНОКПП + генерирует deep-ссылки на реестры Украины
для проверки физлица (борги, виконавчі провадження, суди, декларації, санкції, розшук).

⚠️ Физлицо — обрабатывай только при законном основании (см. ethics-legal.md; стоп-контроль
в скиле person-osint). Энричер НЕ скрейпит и не раскрывает персональные данные — лишь
валидирует идентификатор и даёт точки входа в публичные реестры.
"""
from urllib.parse import quote

from .base import EnricherResult, enricher


def valid_rnokpp(code: str) -> bool:
    """Контрольная сумма РНОКПП/ІПН (10 цифр)."""
    if not code.isdigit() or len(code) != 10:
        return False
    k = [-1, 5, 7, 9, 4, 6, 10, 5, 7]
    d = [int(c) for c in code]
    checksum = (sum(k[i] * d[i] for i in range(9)) % 11) % 10
    return checksum == d[9]


def registry_links(name: str) -> dict[str, str]:
    q = quote(name)
    return {
        "Єдиний реєстр боржників": "https://erb.minjust.gov.ua/  (пошук за ПІБ)",
        "АСВП (виконавчі провадж.)": "https://asvpweb.minjust.gov.ua/  (пошук за ПІБ/ІПН)",
        "Судові рішення (reyestr)": f"https://reyestr.court.gov.ua/?suchau={q}",
        "Декларації НАЗК": f"https://public.nazk.gov.ua/documents/list?q={q}",
        "PEP (публічні діячі)": f"https://pep.org.ua/uk/search?q={q}",
        "Реєстр корупціонерів (НАЗК)": "https://corruptinfo.nazk.gov.ua/  (пошук за ПІБ)",
        "Люстрація (Очищення влади)": "https://lustration.minjust.gov.ua/register",
        "Держреєстр санкцій (РНБО)": "https://drs.nsdc.gov.ua/  (пошук за ПІБ)",
        "Розшук осіб (МВС)": "https://wanted.mvs.gov.ua/",
        "Реєстр банкрутів": "https://bankrutstvo.com.ua/  / через ЄДР",
        "Opendatabot — перевірка фізособи": "https://opendatabot.ua/open/check-person",
        "ЄДЕБО — документи про освіту": "https://info.edbo.gov.ua/edu-documents/  (верифікація диплома)",
    }


@enricher("ua_person_links", "person", country="ua")
def enrich_ua_person(value: str) -> EnricherResult:
    res = EnricherResult("ua_person_links", "person", value)
    val = value.strip()
    root = res.node("person", val, country="ua")

    digits = val.replace(" ", "")
    if digits.isdigit() and len(digits) == 10:
        if valid_rnokpp(digits):
            root.attrs["id_check"] = "РНОКПП (валідний)"
            res.fact(f"РНОКПП {digits}: валідний (контрольна сума зійшлась)",
                     "контрольна сума РНОКПП", "A1")
        else:
            res.fact(f"РНОКПП {digits}: контрольна сума НЕ зійшлась — перевір опечатку",
                     "контрольна сума РНОКПП")
        res.fact("⚠️ РНОКПП — персональні дані. Обробляй лише за наявності підстави.", "ethics-legal")
    else:
        res.fact(f"Вхід трактовано як ПІБ: «{val}». Тримай варіанти транслітерації (укр/лат/рос).",
                 "методологія")

    for name, url in registry_links(val).items():
        res.fact(f"{name}: {url}", "deep-link реєстру")

    res.fact("Далі: person-osint плейбук (перевір підставу!) → ЄРБ/АСВП/reyestr → "
             "декларації/PEP/санкції → зв'язки (бенефіціар? → company-dd).", "person-osint")
    return res
