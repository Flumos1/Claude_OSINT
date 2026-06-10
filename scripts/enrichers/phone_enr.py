"""
Phone-энричер (нейтральный) — оператор/регион/тип номера.

Базовый слой — БЕЗ ключа, офлайн, через библиотеку phonenumbers (порт Google libphonenumber):
страна, регион, оператор, тип (моб/город.), таймзона, валидность. Легально и приватно
(никаких внешних запросов о номере).

Опционально (по ключу NUMVERIFY_API_KEY) — уточнение через numverify.
Поиск публичных упоминаний номера (ФОП/объявления/соцсети) — deep-ссылки. «Пробив» не используем.
"""
import os
from urllib.parse import quote

from .base import EnricherResult, enricher

try:
    import phonenumbers
    from phonenumbers import carrier, geocoder, timezone as ph_tz
    HAVE_PN = True
except ImportError:
    HAVE_PN = False

NUM_TYPE = {0: "стационарный", 1: "мобильный", 2: "моб/город.", 3: "toll-free",
            4: "premium", 5: "shared", 6: "VoIP", 7: "personal", 27: "мобильный"}


@enricher("phone_info", "phone")
def enrich_phone(value: str) -> EnricherResult:
    res = EnricherResult("phone_info", "phone", value)
    raw = value.strip()
    root = res.node("phone", raw)

    if not HAVE_PN:
        res.fact("Нет пакета phonenumbers (pip install phonenumbers) — только deep-ссылки.", "config")
    else:
        n = None
        for region in (None, "UA", "RU"):
            try:
                n = phonenumbers.parse(raw, region)
                if phonenumbers.is_possible_number(n):
                    break
            except Exception:
                n = None
        if n:
            valid = phonenumbers.is_valid_number(n)
            geo = geocoder.description_for_number(n, "ru")
            carr = carrier.name_for_number(n, "ru")
            tzs = ", ".join(ph_tz.time_zones_for_number(n))
            ntype = NUM_TYPE.get(phonenumbers.number_type(n), "?")
            e164 = phonenumbers.format_number(n, phonenumbers.PhoneNumberFormat.E164)
            root.attrs.update({"e164": e164, "region": geo, "carrier": carr, "type": ntype, "valid": valid})
            res.fact(f"Номер {e164}: {'валиден' if valid else 'НЕвалиден'}, {ntype}", "phonenumbers", "B2")
            res.fact(f"Регион: {geo or '—'}; оператор: {carr or '—'}; таймзона: {tzs or '—'}",
                     "phonenumbers", "B2")
        else:
            res.fact(f"Не удалось разобрать номер «{raw}» — укажи в межд. формате (+380…).", "phonenumbers")

    # опционально numverify по ключу
    key = os.getenv("NUMVERIFY_API_KEY")
    if key:
        try:
            import requests
            r = requests.get("http://apilayer.net/api/validate",
                             params={"access_key": key, "number": raw}, timeout=15)
            d = r.json()
            if d.get("valid"):
                res.fact(f"numverify: {d.get('carrier')} / {d.get('line_type')} / {d.get('country_name')}",
                         "numverify API", "B2")
        except Exception as e:
            res.fact(f"numverify ошибка: {e}", "numverify")

    # где номер мог публиковаться (открытые источники)
    q = quote(raw)
    res.fact(f"Публичные упоминания (вручную): https://www.google.com/search?q=%22{q}%22 "
             "(ФОП/объявления/соцсети). «Пробив» по слитым базам не используем.", "методология")
    return res
