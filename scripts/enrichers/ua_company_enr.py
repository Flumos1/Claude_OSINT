"""
UA-энричер компании (приоритетная страна). По коду ЄДРПОУ:
валидирует контрольную сумму + генерирует deep-ссылки на ключевые реестры Украины.

Открытого единого API у ЄДР под капчей нет, поэтому энричер не скрейпит, а валидирует
код и даёт аналитику точные точки входа (Opendatabot/YouControl/reyestr/ProZorro и др.).
Источники и детали — knowledge/sources/ua.md.
"""
from .base import EnricherResult, enricher


def valid_edrpou(code: str) -> bool:
    """Контрольная сумма ЄДРПОУ (8 цифр)."""
    if not code.isdigit() or len(code) != 8:
        return False
    d = [int(c) for c in code]
    num = int(code)
    base = [7, 1, 2, 3, 4, 5, 6] if 30000000 < num < 60000000 else [1, 2, 3, 4, 5, 6, 7]
    checksum = sum(base[i] * d[i] for i in range(7)) % 11
    if checksum == 10:
        shift = [9, 3, 4, 5, 6, 7, 8] if 30000000 < num < 60000000 else [3, 4, 5, 6, 7, 8, 9]
        checksum = sum(shift[i] * d[i] for i in range(7)) % 11
        if checksum == 10:
            checksum = 0
    return checksum == d[7]


def registry_links(ident: str) -> dict[str, str]:
    return {
        "ЄДР (Мін'юст)": "https://usr.minjust.gov.ua/content/free-search",
        "Opendatabot": f"https://opendatabot.ua/c/{ident}",
        "YouControl": f"https://youcontrol.com.ua/catalog/company_details/{ident}/",
        "Clarity Project": f"https://clarity-project.info/edr/{ident}",
        "Судові рішення (reyestr)": f"https://reyestr.court.gov.ua/?suchau={ident}",
        "Єдиний реєстр боржників": "https://erb.minjust.gov.ua/",
        "АСВП (виконавчі провадж.)": "https://asvpweb.minjust.gov.ua/",
        "ProZorro (закупівлі)": f"https://prozorro.gov.ua/search/tender?edrpou={ident}",
        "DoZorro (ризики)": f"https://dozorro.org/company/{ident}",
        "Держреєстр санкцій (РНБО)": "https://drs.nsdc.gov.ua/",
    }


@enricher("ua_company_links", "company", country="ua")
def enrich_ua_company(value: str) -> EnricherResult:
    res = EnricherResult("ua_company_links", "company", value)
    ident = value.strip().replace(" ", "")
    root = res.node("company", ident, country="ua")

    if len(ident) == 8 and valid_edrpou(ident):
        kind = "ЄДРПОУ (валідний)"
        conf = "A1"
    elif ident.isdigit() and len(ident) == 8:
        kind = "8 цифр, але контрольна сума НЕ зійшлась — перевір опечатку"
        conf = ""
    elif ident.isdigit():
        kind = f"{len(ident)} цифр — не схоже на ЄДРПОУ (очікується 8); можливо назва/інший ID"
        conf = ""
    else:
        kind = "не числовий ID — пошук за назвою"
        conf = ""

    root.attrs["id_check"] = kind
    res.fact(f"Ідентифікатор {ident}: {kind}", "контрольна сума ЄДРПОУ", conf)

    for name, url in registry_links(ident).items():
        res.fact(f"{name}: {url}", "deep-link реєстру")

    res.fact("Далі: company-dd плейбук, 🇺🇦 швидкий маршрут (ЄДР → суди → борги → "
             "ProZorro → санкції → бенефіціари/НАЗК → нерухомість).", "company-dd")
    return res
