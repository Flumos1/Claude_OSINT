"""
RU-энричер компании — наш дифференциатор (во flowsint/awesome-osint RU-реестров нет).

По ИНН или ОГРН: проверяет контрольную сумму (валидность идентификатора) и генерирует
готовые deep-ссылки на ключевые реестры РФ для ручной/браузерной проверки.

Прямого открытого API у ЕГРЮЛ нет (egrul.nalog.ru с капчей), поэтому энричер не
скрейпит, а валидирует ID и даёт аналитику точные точки входа. Это безопасно и легально.
"""
from .base import EnricherResult, enricher


def valid_inn(inn: str) -> bool:
    if not inn.isdigit():
        return False
    d = [int(x) for x in inn]
    if len(inn) == 10:
        w = [2, 4, 10, 3, 5, 9, 4, 6, 8]
        return (sum(w[i] * d[i] for i in range(9)) % 11) % 10 == d[9]
    if len(inn) == 12:
        w1 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        w2 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        c1 = (sum(w1[i] * d[i] for i in range(10)) % 11) % 10
        c2 = (sum(w2[i] * d[i] for i in range(11)) % 11) % 10
        return c1 == d[10] and c2 == d[11]
    return False


def valid_ogrn(ogrn: str) -> bool:
    if not ogrn.isdigit():
        return False
    if len(ogrn) == 13:
        return int(ogrn[:12]) % 11 % 10 == int(ogrn[12])
    if len(ogrn) == 15:  # ОГРНИП
        return int(ogrn[:14]) % 13 % 10 == int(ogrn[14])
    return False


def registry_links(ident: str) -> dict[str, str]:
    return {
        "ЕГРЮЛ/ЕГРИП (ФНС)": f"https://egrul.nalog.ru/index.html?query={ident}",
        "Прозрачный бизнес": f"https://pb.nalog.ru/search.html?mode=search-ul&queryUl={ident}",
        "Rusprofile": f"https://www.rusprofile.ru/search?query={ident}",
        "Checko": f"https://checko.ru/search?query={ident}",
        "Арбитраж (kad.arbitr)": "https://kad.arbitr.ru/  (поиск по ИНН/названию)",
        "ФССП (долги)": "https://fssp.gov.ru/iss/ip  (поиск по ЮЛ)",
        "Банкротство (Федресурс)": f"https://bankrot.fedresurs.ru/search/?searchString={ident}",
        "Госзакупки": f"https://zakupki.gov.ru/epz/main/public/search/search.html?searchString={ident}",
        "ГИР БО (отчётность)": f"https://bo.nalog.ru/search?query={ident}",
    }


@enricher("ru_company_links", "company", country="ru")
def enrich_ru_company(value: str) -> EnricherResult:
    res = EnricherResult("ru_company_links", "company", value)
    ident = value.strip().replace(" ", "")
    root = res.node("company", ident)

    kind = None
    if len(ident) in (10, 12) and valid_inn(ident):
        kind = "ИНН (валиден)"
    elif len(ident) in (13, 15) and valid_ogrn(ident):
        kind = "ОГРН/ОГРНИП (валиден)"
    elif ident.isdigit():
        kind = "идентификатор НЕ прошёл контрольную сумму — проверь опечатку"
    else:
        kind = "не числовой ID — поиск по названию"

    root.attrs["id_check"] = kind
    res.fact(f"Идентификатор {ident}: {kind}", "контрольная сумма ИНН/ОГРН",
             "A1" if "валиден" in kind else "")

    for name, url in registry_links(ident).items():
        res.fact(f"{name}: {url}", "deep-link реестра")

    res.fact("Дальше: company-dd плейбук (регистрация → достоверность → суды → "
             "банкротство → бенефициары → санкции).", "company-dd")
    return res
