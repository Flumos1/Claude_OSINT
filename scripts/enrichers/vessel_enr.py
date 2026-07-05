"""
Энричер vessel (нейтральный) — трекинг МОРСКОГО СУДНА (актива), не людей на борту.

⚖️ Легальная морская OSINT: AIS — публично вещаемый судном сигнал. Отслеживаем судно по
номеру IMO / MMSI / названию (для санкционного мониторинга, DD судовладельцев,
расследований «чьё это судно / где ходило»). НЕ пробив экипажа/пассажиров.

Честно про доступ: живой AIS в основном ключевой/платный (MarineTraffic/VesselFinder).
Поэтому по умолчанию энричер:
  • валидирует IMO по контрольной цифре;
  • даёт deep-ссылки на реестры (Equasis: власник/менеджер/прапор; трекеры позиции);
  • при наличии ключа AISSTREAM_API_KEY — заготовка под живую позицию (подключается позже).
"""
import os
import re

from .base import EnricherResult, enricher

IMO_RX = re.compile(r"^(?:IMO)?\s*(\d{7})$", re.I)
MMSI_RX = re.compile(r"^\d{9}$")


def valid_imo(num: str) -> bool:
    """Контрольная цифра IMO: сумма 6 цифр × (7..2), последняя цифра суммы = 7-я цифра."""
    m = IMO_RX.match(num.strip())
    if not m:
        return False
    d = m.group(1)
    checksum = sum(int(d[i]) * (7 - i) for i in range(6)) % 10
    return checksum == int(d[6])


def _registry_links(ident: str) -> dict[str, str]:
    q = ident.strip()
    imo = IMO_RX.match(q)
    imo_digits = imo.group(1) if imo else q
    search_q = imo_digits if imo else q  # для IMO-входа ищем по цифрам, а не по «IMO 12345»
    return {
        "Equasis (власник/менеджер/прапор)": "https://www.equasis.org/",
        "MarineTraffic": f"https://www.marinetraffic.com/en/ais/details/ships/imo:{imo_digits}",
        "VesselFinder": f"https://www.vesselfinder.com/vessels?name={search_q}",
        "BalticShipping": f"https://www.balticshipping.com/vessel/imo/{imo_digits}",
        "GISIS (IMO)": "https://gisis.imo.org/Public/Default.aspx",
        "OpenSanctions (судна)": f"https://www.opensanctions.org/search/?q={search_q}",
    }


@enricher("vessel_track", "vessel")
def enrich_vessel(value: str) -> EnricherResult:
    res = EnricherResult("vessel_track", "vessel", value)
    ident = value.strip()
    root = res.node("vessel", ident.upper())
    res.fact("⚖️ Трекинг судна (актива), не экипажа/пассажиров. AIS публичен; используй при "
             "правовом основании.", "ethics-legal")

    imo = IMO_RX.match(ident)
    if imo:
        ok = valid_imo(ident)
        root.attrs["imo"] = imo.group(1)
        res.fact(f"IMO {imo.group(1)}: контрольна цифра {'зійшлась (валідний)' if ok else 'НЕ зійшлась — перевір опечатку'}",
                 "IMO checksum", "A1" if ok else "")
    elif MMSI_RX.match(ident):
        root.attrs["mmsi"] = ident
        res.fact(f"Схоже на MMSI ({ident}) — 9 цифр. Для власника резолвни IMO через реестр.",
                 "vessel")
    else:
        res.fact("Дано не IMO/MMSI, а назва — пошук за назвою в реестрах нижче "
                 "(назви не унікальні, звіряй прапор/IMO).", "vessel")

    for name, url in _registry_links(ident).items():
        res.fact(f"Реестр/трекер: {name} — {url}", "deep-link")

    if os.getenv("AISSTREAM_API_KEY"):
        res.fact("AISSTREAM_API_KEY задано — живий AIS підключається окремим модулем "
                 "(websocket aisstream.io). Заготовка.", "config")
    else:
        res.fact("Живий AIS (позиція/трек) — здебільшого за ключем/платно "
                 "(MarineTraffic/VesselFinder API або aisstream.io). Без ключа — реестри вище.",
                 "vessel")
    return res
