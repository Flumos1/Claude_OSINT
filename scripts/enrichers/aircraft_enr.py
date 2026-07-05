"""
Энричер aircraft (нейтральный, keyless) — трекинг ВОЗДУШНОГО СУДНА (актива), не пассажира.

⚖️ Легальная авиа-OSINT: ADS-B — публично вещаемый бортом сигнал. Отслеживаем самолёт по
бортовому/регистрационному номеру или ICAO24-hex (для корпоративного DD, санкционного
мониторинга, расследований «чей это джет / куда летал этот борт»). НЕ пробив пассажиров.

Источник: OpenSky Network REST API (keyless, лимитирован). По ICAO24-hex:
  • текущий вектор состояния (states/all) — если борт в воздухе;
  • недавние рейсы (flights/aircraft за окно) — аэропорты вылета/прилёта + время.
По tail-number (напр. UR-ABC, N123AB) — deep-ссылки на реестры для резолва владельца/hex.
"""
import re
import time

import requests

from .base import EnricherResult, enricher

API = "https://opensky-network.org/api"
TIMEOUT = 20
HEADERS = {"User-Agent": "osint-aircraft-enricher/1.0"}
HEX_RX = re.compile(r"^[0-9a-f]{6}$", re.I)
WINDOW_DAYS = 7


def _registry_links(ident: str) -> dict[str, str]:
    q = ident.strip().upper()
    return {
        "OpenSky metadata": f"https://opensky-network.org/aircraft-profile?icao24={ident.lower()}",
        "Planespotters": f"https://www.planespotters.net/search?q={q}",
        "FlightAware": f"https://www.flightaware.com/live/flight/{q}",
        "JetPhotos": f"https://www.jetphotos.com/registration/{q}",
        "ADS-B Exchange": f"https://globe.adsbexchange.com/?reg={q}",
        "FAA (N-numbers, США)": "https://registry.faa.gov/aircraftinquiry/",
    }


def _airport(res, root, icao_code: str, rel: str):
    if not icao_code:
        return
    n = res.node("airport", icao_code, icao=icao_code)
    res.edge(root, n, rel)


@enricher("aircraft_track", "aircraft")
def enrich_aircraft(value: str) -> EnricherResult:
    res = EnricherResult("aircraft_track", "aircraft", value)
    ident = value.strip()
    root = res.node("aircraft", ident.upper() if not HEX_RX.match(ident) else ident.lower())
    res.fact("⚖️ Трекинг ВС (актива), не пассажира. Используй при правовом основании; "
             "данные ADS-B публичны.", "ethics-legal")

    for name, url in _registry_links(ident).items():
        res.fact(f"Реестр/трекер: {name} — {url}", "deep-link")

    if not HEX_RX.match(ident):
        res.fact("Дано не ICAO24-hex (6 hex-символов), а рег/бортовой номер — резолвни hex "
                 "через реестр выше, затем запусти по hex для живых данных OpenSky.", "aircraft")
        return res

    hexid = ident.lower()
    # текущее состояние (если в воздухе)
    try:
        r = requests.get(f"{API}/states/all", params={"icao24": hexid},
                         headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            states = (r.json() or {}).get("states") or []
            if states:
                s = states[0]
                callsign = (s[1] or "").strip()
                lon, lat, alt, on_ground = s[5], s[6], s[7], s[8]
                root.attrs.update({"callsign": callsign, "on_ground": on_ground})
                res.fact(f"Зараз у ефірі: callsign «{callsign or '—'}», "
                         f"позиція {lat},{lon}, висота {alt} м, on_ground={on_ground}",
                         "OpenSky states", "B2")
            else:
                res.fact("Зараз не віщає (не в повітрі або поза покриттям ADS-B).",
                         "OpenSky states", "C3")
    except Exception as e:
        res.error = str(e)

    # недавние рейсы за окно
    try:
        end = int(time.time())
        begin = end - WINDOW_DAYS * 86400
        r = requests.get(f"{API}/flights/aircraft",
                         params={"icao24": hexid, "begin": begin, "end": end},
                         headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            flights = r.json() or []
            res.fact(f"Рейсів за {WINDOW_DAYS} діб: {len(flights)}", "OpenSky flights", "B2")
            for fl in flights[:10]:
                dep = fl.get("estDepartureAirport")
                arr = fl.get("estArrivalAirport")
                t = time.strftime("%Y-%m-%d %H:%M", time.gmtime(fl.get("firstSeen", 0)))
                _airport(res, root, dep, "departed_from")
                _airport(res, root, arr, "arrived_at")
                res.fact(f"{t}Z  {dep or '?'} → {arr or '?'}", "OpenSky flights", "B2")
        elif r.status_code == 404:
            res.fact("Рейсів за вікно не знайдено (404) — борт міг не літати або поза покриттям.",
                     "OpenSky flights", "C3")
    except Exception as e:
        if not res.error:
            res.error = str(e)
    return res
