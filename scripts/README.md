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
| `person_search.py` + `translit.py` | Интеллектуальный поиск ФЛ: варианты имени, реестры UA/RU/межд., живой НАЗК | не нужен |
| `dorks.py` | Генератор Google/Bing/Yandex дорков для домена и персоны | не нужен |
| `secrets_scan.py` | Каталог secret-regex (24) + скан URL/файла на утёкшие секреты | не нужен |
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
```

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
| `opendatabot` | company [ua] | Opendatabot API (карточка компании) | ODB_API_KEY |
| `ua_person_links` | person [ua] | валидация РНОКПП + ссылки (ЄРБ/АСВП/reyestr…) | — |
| `nazk_declarations` | person [ua] | **НАЗК API** (декларації посадовців) | — ✅ |
| `ru_company_links` | company [ru] | валидация ИНН/ОГРН + ссылки на реестры РФ | — |
| `domain_recon` | domain | RDAP/crt.sh/DNS/Wayback + дорки | — |
| `website` | domain | SSL-сертификат, security-заголовки, сервер, robots/security.txt (web-check-стиль) | — ✅ |
| `typosquat` | domain | типо-варианты домена + IDN-омоглифы, DNS-проверка живых (dnstwist-стиль) | — ✅ |
| `secrets_scan` | url | скан страницы на утёкшие секреты (24 паттерна) | — ✅ |
| `ip_geo_asn` | ip | гео/ASN (ip-api) | — |
| `email_gravatar` | email | Gravatar + пивот в домен | — |
| `email_leaks` | email | HIBP (присутствие в утечках) | HIBP_API_KEY |
| `phone_info` | phone | оператор/регион/тип (офлайн phonenumbers) | — ✅ |
| `username_sweep` | username | быстрый чек ника по 12 платформам | — ✅ |

✅ = бесплатно, без ключа, работает «из коробки».

## Бэклог энричеров (по образцу каталога flowsint)

🇺🇦 **Украина:** `opendatabot` расширить (CourtService/PenaltyService/RealEstateService по ключу);
`youcontrol` (YouScore API, по ключу).
**Нейтральные (которых нет, приоритет по flowsint):** `domain.ssl/whois_history`,
`ip.ports` (Shodan), `username.maigret` (глубже sweep), `phone.carrier`,
`email.leaks` (HIBP, свои/авторизованные), `crypto`, `ioc` (VT/AbuseIPDB/GreyNoise),
`archive_page` (Playwright/Wayback).

> Принцип: пассивные источники по умолчанию; ключи и .env — вне репозитория;
> результаты складывай в `cases/<slug>/data/`. Полный список flowsint-энричеров как
> референс — [flowsint-integration.md](../knowledge/flowsint-integration.md).
