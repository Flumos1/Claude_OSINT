"""
RU-энричер физлица — паритет с UA-слоем. По ФИО или ИНН (12-значный, физлицо):
валидирует контрольную сумму ИНН + генерирует deep-ссылки на реестры РФ для проверки
физлица (исп. производства, банкротство, суды, розыск, дисквалификация, экстремисты).

⚠️ Физлицо — только при законном основании (KYC/DD/взыскание/расследование). Энричер НЕ
скрейпит и не раскрывает персональные данные — валидирует идентификатор и даёт точки входа
в публичные реестры. «Пробив»/слитые базы/паспортные данные — вне рамок (ethics-legal.md).
Многие RU-реестры под капчей и требуют ФИО+дату рождения для точности.
"""
from urllib.parse import quote

from .base import EnricherResult, enricher
from .ru_company_enr import valid_inn


def registry_links(name: str) -> dict[str, str]:
    q = quote(name)
    return {
        "ФССП (исп. производства)": "https://fssp.gov.ru/iss/ip  (ФИО + дата рождения)",
        "Банкротство физлиц (Федресурс)": f"https://bankrot.fedresurs.ru/bankrupts?searchString={q}",
        "Суды (ГАС Правосудие)": "https://bsr.sudrf.ru/bigs/portal.html  (судебные акты по ФИО)",
        "Прозрачный бизнес (ФНС)": "https://pb.nalog.ru/  (дисквалификация / статус ИП)",
        "Реестр дисквалифицированных (ФНС)": "https://service.nalog.ru/disqualified.do",
        "ЕГРИП (если ИП)": "https://egrul.nalog.ru/  (ИП по ФИО/ИНН)",
        "Розыск МВД": "https://xn--b1aew.xn--p1ai/wanted",
        "Экстремисты/террористы (Росфинмониторинг)": "http://www.fedsfm.ru/documents/terrorists-catalog-portal-act",
        "Реестр иноагентов (Минюст)": "https://minjust.gov.ru/ru/activity/directions/998/",
    }


@enricher("ru_person_links", "person", country="ru")
def enrich_ru_person(value: str) -> EnricherResult:
    res = EnricherResult("ru_person_links", "person", value)
    val = value.strip()
    root = res.node("person", val, country="ru")

    digits = val.replace(" ", "")
    if digits.isdigit() and len(digits) == 12:
        if valid_inn(digits):
            root.attrs["id_check"] = "ИНН физлица (валиден)"
            res.fact(f"ИНН {digits}: валиден (12-знач., контрольные суммы сошлись)",
                     "контрольная сумма ИНН", "A1")
        else:
            res.fact(f"ИНН {digits}: контрольная сумма НЕ сошлась — проверь опечатку",
                     "контрольная сумма ИНН")
        res.fact("⚠️ ИНН — персональные данные. Обрабатывай только при основании.", "ethics-legal")
    elif digits.isdigit() and len(digits) == 10:
        res.fact(f"{digits} — 10 цифр: это ИНН ЮРЛИЦА, не физлица. Для компании → "
                 "enrich.py company … -c ru.", "методология")
    else:
        res.fact(f"Вход трактован как ФИО: «{val}». Держи варианты транслитерации (рус/лат). "
                 "Для ФССП/судов нужна дата рождения.", "методология")

    for name, url in registry_links(val).items():
        res.fact(f"{name}: {url}", "deep-link реестра")

    res.fact("Дальше: person-osint плейбук (проверь основание!) → ФССП/банкротство/суды → "
             "розыск/санкции → связи (ИП/учредитель? → company-dd).", "person-osint")
    return res
