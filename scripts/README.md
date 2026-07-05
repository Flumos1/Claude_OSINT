# Scripts

Утилиты автоматизации сбора. Запуск из этой папки.

## Установка

```powershell
cd "G:\Claude OSINT\scripts"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # затем заполни ключи (опционально)
```

## Утилиты

| Скрипт | Назначение | API-ключ |
|--------|-----------|----------|
| `domain_recon.py` | RDAP + crt.sh поддомены + DNS + Wayback по домену | не нужен |
| `fetch_awesome_osint.py` | Локальный индекс 1400+ инструментов из awesome-osint + поиск | не нужен |
| `enrich.py` + `enrichers/` | Раннер энричеров (по мотивам flowsint): сущность → граф | не нужен |
| `person_search.py` + `translit.py` | Одношаговый поиск ФЛ: варианты имени, реестры UA/RU/межд., живой НАЗК | не нужен |
| `person_recon.py` | **Многошаговая разведка личности**: итеративный пивотинг + движок корреляции (тиры достоверности), гейт основания | не нужен |
| `dorks.py` | Генератор Google/Bing/Yandex дорков для домена и персоны | не нужен |
| `secrets_scan.py` | Каталог secret-regex (24) + скан URL/файла на утёкшие секреты | не нужен |
| `analyze.py` + `osint_graph.py` | **Аналитика графа**: слияние сущностей, риск-флаги, выводы/гипотезы, таймлайн, бриф | не нужен |
| `image_tools.py` | Аватар-пивот: reverse-image ссылки + опц. pHash (сверка лиц между платформами) | не нужен |
| `typosquat.py` | Генератор типо-вариантов домена (dnstwist-стиль) + IDN-омоглифы + DNS-проверка | не нужен |

```powershell
# Разведка по домену
python domain_recon.py example.com --json ..\cases\<slug>\data\example.com.json

# Обновить локальный каталог инструментов (→ knowledge/tools-index.md + .json)
python fetch_awesome_osint.py
# Поиск инструмента по локальному индексу
python fetch_awesome_osint.py --search username

# Типосквоттинг/брендозащита: похожие домены + кто из них уже зарегистрирован
python typosquat.py example.com --resolve --json ..\cases\<slug>\data\typosquat.json

# Энричеры: обогащение сущности до графа (узлы/связи/факты)
python enrich.py --list
python enrich.py domain example.com --json ..\cases\<slug>\data\graph.json
python enrich.py company 14360570         # 🇺🇦 ЄДРПОУ (по умолчанию --country ua)
python enrich.py company 7707083893 -c ru # 🇷🇺 ИНН/ОГРН
python enrich.py ip 8.8.8.8
python enrich.py email user@example.com
python enrich.py username johndoe          # username_sweep + github_user (ник→особа)
python enrich.py aircraft 3c6444           # ⚖️ трекинг борта (ICAO24-hex): OpenSky + реестры
python enrich.py aircraft UR-PSR           # бортовой номер → deep-ссылки на реестры

# Многошаговая разведка личности (⚖️ только по правовому основанию!)
#   Итеративно пивотит сиды (email→gravatar→домен, ник→github→commit-email/сайт/twitter…),
#   строит граф и КОРРЕЛИРУЕТ достоверность связи (CONFIRMED/PROBABLE/POSSIBLE).
python person_recon.py --basis "KYC контрагента X" --name "Іван Іваненко" \
    --email a@b.com --username ivanko --github ivanko --hops 2 \
    --json ..\cases\<slug>\data\recon.json --report ..\cases\<slug>\recon.md
```

> `person_recon.py` не запустится без `--basis` (гейт правового основания зашит в код).
> Только открытые источники; тиры достоверности — против ложной атрибуции (ник ≠ человек).

```powershell
# Аналитика поверх графа: слияние сущностей + риски + выводы/гипотезы + таймлайн + бриф
python person_recon.py --basis "..." --name "..." --username u --json g.json
python analyze.py --graph g.json --report brief.md
python analyze.py --enrich company 14360570         # собрать граф и сразу проанализировать

# Аватар-пивот (сверка лица между платформами; pHash — если установлен pillow)
python image_tools.py compare <url_avatar1> <url_avatar2>
```

> Аналитика прозрачна: **факт** остаётся фактом со ссылкой, **вывод/гипотеза** помечаются
> (INFERENCE/HYPOTHESIS). Риск-флаги считаются только по содержательным наблюдениям, не по
> deep-ссылкам. `pillow` — опционален (без него аватар-пивот даёт reverse-image ссылки).

Страновые энричеры (`company`) выбираются флагом `-c/--country` (по умолчанию `ua`).
Нейтральные (`domain/ip/email`) работают для любой страны. Добавить страну —
см. [knowledge/sources/README.md](../knowledge/sources/README.md).

## Архитектура энричеров

`enrichers/` — модули по контракту «сущность → граф», по мотивам flowsint
(см. [knowledge/flowsint-integration.md](../knowledge/flowsint-integration.md)).
Граф-вывод (nodes/edges) совместим с Neo4j — позже импортируем во flowsint.
Добавить энричер: файл в `enrichers/`, функция `fn(value)->EnricherResult` с
`@enricher("имя","тип")`, импорт в `enrichers/__init__.py`.

## Реализованные энричеры

| Энричер | Тип [страна] | Источник | Ключ |
|---------|--------------|----------|------|
| `ua_company_links` | company [ua] | валидация ЄДРПОУ + ссылки на реестры | — |
| `prozorro` | company [ua] | **ProZorro API** (тендеры по коду) | — ✅ |
| `opendatabot` | company [ua] | Opendatabot API: карточка + доп. сервіси (суди/штрафи/нерухомість) | ODB_API_KEY |
| `youcontrol` | company [ua] | YouControl/YouScore (карточка, бенефіціари); без ключа — deep-ссылка | YOUCONTROL_API_KEY |
| `ua_person_links` | person [ua] | валидация РНОКПП + ссылки (ЄРБ/АСВП/reyestr…) | — |
| `nazk_declarations` | person [ua] | **НАЗК API** (декларації посадовців) | — ✅ |
| `ru_company_links` | company [ru] | валидация ИНН/ОГРН + ссылки на реестры РФ | — |
| `domain_recon` | domain | RDAP/crt.sh/DNS/Wayback + дорки | — |
| `website` | domain | SSL-сертификат, security-заголовки, сервер, robots/security.txt (web-check-стиль) | — ✅ |
| `typosquat` | domain | типо-варианты домена + IDN-омоглифы, DNS-проверка живых (dnstwist-стиль) | — ✅ |
| `secrets_scan` | url | скан страницы на утёкшие секреты (24 паттерна) | — ✅ |
| `aircraft_track` | aircraft | ⚖️ трекинг ВС (актива, не пассажира): OpenSky состояние + рейсы по ICAO24 + реестры | — ✅ |
| `ip_geo_asn` | ip | гео/ASN (ip-api) | — |
| `github_user` | username | ник → ім'я/компанія/сайт/twitter + email з публічних комітів + аватар-пивот | — ✅ |
| `email_gravatar` | email | Gravatar (профиль, аккаунты) + пивот в домен + аватар/reverse-image | — |
| `email_accounts` | email | существование по email (Gravatar/Libravatar, штатно) + tool-пивот holehe/epieos | — ✅ |
| `email_leaks` | email | HIBP (присутствие в утечках) | HIBP_API_KEY |
| `phone_info` | phone | оператор/регион/тип (офлайн phonenumbers) | — ✅ |
| `username_sweep` | username | чек ника по ~48 платформам (категории) + опц. датасет WhatsMyName | — ✅ |

✅ = бесплатно, без ключа, работает «из коробки».

> **username_sweep, глубокий режим:** положи датасет [WhatsMyName](https://github.com/WebBreacher/WhatsMyName)
> в `scripts/data/wmn-data.json` — энричер автоматически прогонит сотни сайтов поверх
> курируемого списка (maigret-уровень, keyless). Без файла — работает на курируемых ~48.
> Файл не коммитим (см. `.gitignore`).

## Бэклог энричеров (по образцу каталога flowsint)

**Нейтральные (которых нет, приоритет по flowsint):** `domain.ssl/whois_history`,
`ip.ports` (Shodan InternetDB — keyless), `phone.carrier`, `crypto`,
`ioc` (VT/AbuseIPDB/GreyNoise), `archive_page` (Wayback CDX).

> Принцип: пассивные источники по умолчанию; ключи и .env — вне репозитория;
> результаты складывай в `cases/<slug>/data/`. Полный список flowsint-энричеров как
> референс — [flowsint-integration.md](../knowledge/flowsint-integration.md).
