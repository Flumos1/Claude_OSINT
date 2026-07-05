# Источники: международные

> Публичные/официальные ресурсы. Доступность и условия меняются — проверяй на дату.

## Компании и корпоративные реестры

| Источник | URL | Что даёт |
|----------|-----|----------|
| OpenCorporates | opencorporates.com | Крупнейшая открытая БД компаний по юрисдикциям |
| GLEIF (LEI) | gleif.org | Глобальный идентификатор юрлица, оргструктура |
| SEC EDGAR (США) | sec.gov/edgar | Отчётность публичных компаний США, инсайдеры, форма 10-K/8-K |
| Companies House (UK) | find-and-update.company-information.service.gov.uk | Реестр UK: директора, бенефициары (PSC), отчётность |
| Реестры по странам | напр. Handelsregister (DE), Infogreffe (FR), ASIC (AU) | Нац. корпоративные данные |
| North Data | northdata.com | Европа: связи, публикации, сети |

## Расследовательские базы / leaks

| Источник | URL | Что даёт |
|----------|-----|----------|
| OCCRP Aleph | aleph.occrp.org | Агрегатор документов, реестров, утечек для журналистов |
| ICIJ Offshore Leaks | offshoreleaks.icij.org | Panama/Paradise/Pandora Papers — офшоры, бенефициары |
| LittleSis | littlesis.org | «Кто кого знает» — связи людей и корпораций (США) |
| OpenSanctions | opensanctions.org | Объединённые санкционные/PEP-списки, поиск по сущностям |

## Санкции, PEP, комплаенс

| Источник | URL | Покрытие |
|----------|-----|----------|
| OFAC SDN (США) | sanctionssearch.ofac.treas.gov | Список заблокированных лиц США |
| EU Sanctions Map | sanctionsmap.eu | Санкции ЕС |
| UK Sanctions List | gov.uk/government/publications/financial-sanctions-consolidated-list-of-targets | OFSI |
| UN Consolidated | un.org/securitycouncil/content/un-sc-consolidated-list | Санкции ООН |
| OpenSanctions | opensanctions.org | Всё вышеперечисленное + PEP, в одном поиске + API |
| World-Check / Dow Jones | коммерческие | Глубокий комплаенс (платно) |

## Домены, DNS, инфраструктура

| Источник | URL | Что даёт |
|----------|-----|----------|
| WHOIS / RDAP | rdap.org, who.is | Регистрант, даты, регистратор, серверы имён |
| crt.sh | crt.sh | Certificate Transparency: поддомены, история сертификатов |
| SecurityTrails | securitytrails.com | История DNS/whois, поддомены (free tier) |
| ViewDNS | viewdns.info | Reverse IP/whois, история, набор утилит |
| DNSdumpster / dnsdumpster.com | dnsdumpster.com | Карта DNS, поддомены |
| Shodan | shodan.io | Открытые порты/сервисы/баннеры по IP, устройства |
| Censys | search.censys.io | Аналог Shodan, сертификаты, хосты |
| FOFA / ZoomEye | fofa.info / zoomeye.org | Поиск по интернет-активам (CN) |
| Wayback Machine | web.archive.org | Исторические снимки сайтов |
| urlscan.io | urlscan.io | Скан страницы: ресурсы, редиректы, скриншот, связи |
| BGP / ASN | bgp.he.net | ASN, префиксы, peering |

## Threat intel / утечки / репутация

| Источник | URL | Что даёт |
|----------|-----|----------|
| Have I Been Pwned | haveibeenpwned.com | В каких утечках засветился email/домен (API) |
| Intelligence X | intelx.io | Поиск по leaks, darkweb, документам (free/paid) |
| DeHashed | dehashed.com | Поиск по утечкам (платно) — только для своих/авторизованных данных |
| VirusTotal | virustotal.com | Репутация файла/URL/домена/IP, пассивный DNS |
| AbuseIPDB | abuseipdb.com | Репутация IP (жалобы) |
| AlienVault OTX | otx.alienvault.com | Сообщество IOC, пульсы |
| GreyNoise | greynoise.io | Фоновый интернет-шум: сканер это или таргет |
| URLhaus / MalwareBazaar | abuse.ch | Вредоносные URL/семплы |
| ThreatFox | threatfox.abuse.ch | IOC по угрозам |

## Люди, ники, соцсети, медиа

| Источник | URL | Что даёт |
|----------|-----|----------|
| Reverse image | Google Lens, Yandex Images, TinEye, Bing Visual | Где встречалось изображение |
| Username search | whatsmyname.app, Sherlock (CLI), Maigret | Аккаунты по нику на N платформах |
| Email→accounts | Holehe (CLI), EmailRep | Где зарегистрирован email |
| Phone | PhoneInfoga (CLI), numverify | Оператор, регион, формат |
| GitHub | github.com search, gitleaks | Код, утечки секретов, email из коммитов |
| Geo | Google Earth, Mapillary, SunCalc, Overpass Turbo (OSM) | Гео/хронолокация |

## Авиация и транспорт (⚖️ легально: борты/суда, НЕ пассажиры)

> Отслеживаем **воздушное/морское судно как актив** (для DD, санкций, расследований
> «чей джет / куда летал этот борт»), а не перелёты частных лиц. ADS-B/AIS —
> публично вещаемые сигналы. Пробив пассажиров по ФИО (PNR/«базы авиабилетов») —
> вне закона и вне наших рамок (см. [ethics-legal.md](../ethics-legal.md)).

| Источник | URL | Что даёт |
|----------|-----|----------|
| ADS-B Exchange | globe.adsbexchange.com | Трекинг ВС без фильтров (в т.ч. частные/military), поиск по reg/hex |
| OpenSky Network | opensky-network.org | **Открытый API (keyless)**: состояние борта + история рейсов по ICAO24 |
| Flightradar24 | flightradar24.com | Живой трекинг, история (частично платно) |
| Planespotters / JetPhotos | planespotters.net, jetphotos.com | Борт → тип, оператор, история, фото |
| FAA Registry (США) | registry.faa.gov/aircraftinquiry | N-number → владелец/оператор |
| ICAO24 ↔ reg | opensky-network.org/aircraft-profile | Резолв hex ↔ бортовой номер |
| MarineTraffic / VesselFinder | marinetraffic.com, vesselfinder.com | Морские суда (AIS): позиция, история, владелец |
| Эквасис (IMO) | equasis.org | Судно по IMO: собственник, менеджер, флаг |

> Скрипт: `python scripts/enrich.py aircraft <ICAO24-hex|бортовой_номер>` — живой OpenSky
> (состояние + недавние рейсы) + deep-ссылки на реестры; борт пивотится в узел
> оператора/компании для корпоративного DD.

## Поисковые техники (Google/Yandex dorking)

- `site:` `inurl:` `intitle:` `filetype:` `"точная фраза"` `-исключение` `OR` `*`
- Утечки документов: `filetype:pdf|xlsx|docx site:target.com`
- Поддиректории: `site:target.com -www`
- Поиск ника/почты в кавычках по нескольким движкам (Google, Yandex, Bing, DuckDuckGo, Brave).
- Спец. движки: Pipl-аналоги, intelx, публичные пасты (psbdmp).

## API-ключи (если будут использоваться)

Храни в `scripts/.env` (не коммитить). Полезные free-tier: HIBP, Shodan, urlscan,
VirusTotal, SecurityTrails, OpenSanctions. См. scripts/README.md.
