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
| `fetch_wmn.py` | Датасет WhatsMyName (700+ сайтов) для deep-режима username | не нужен |

```powershell
# Разведка по домену
python domain_recon.py example.com --json ..\cases\<slug>\data\example.com.json

# Обновить локальный каталог инструментов (→ knowledge/tools-index.md + .json)
python fetch_awesome_osint.py
# Поиск инструмента по локальному индексу
python fetch_awesome_osint.py --search username

# Энричеры: обогащение сущности до графа (узлы/связи/факты)
python enrich.py --list
python enrich.py domain example.com --json ..\cases\<slug>\data\graph.json
python enrich.py company 14360570         # 🇺🇦 ЄДРПОУ (по умолчанию --country ua)
python enrich.py company 7707083893 -c ru # 🇷🇺 ИНН/ОГРН
python enrich.py ip 8.8.8.8
python enrich.py email user@example.com

# Username: быстрый чек — 21 куратируемая + WhatsMyName (~700, датасет уже в репо)
python enrich.py username johndoe
# Глубокий чек — тот же пул + Maigret + Sherlock (датасеты тоже в репо, дедуп по домену)
$env:USERNAME_DEEP=1; python enrich.py username johndoe   # PowerShell
# Обновить датасеты (не обязательно — уже закоммичены и бандлятся на Vercel):
python fetch_wmn.py
# Тюнинг: USERNAME_POOL_CAP, USERNAME_FAST_BUDGET/USERNAME_DEEP_BUDGET (wall-clock, безопасно
# под Vercel maxDuration), USERNAME_DEEP_WORKERS, USERNAME_DEEP_TIMEOUT
```

> **Скоринг username:** каждое попадание получает уверенность 0–100% и Admiralty-оценку
> (D3 ≥78% / D4 55–77% / D5 <55%). Буква `D` — источник-скрейпер ненадёжен по природе;
> цифра двигается по силе детекта. Режет soft-404 (HTTP 200 на любой ник, редиректы
> на login/главную) — фокусируй ручную проверку на хитах низкой уверенности.

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
| `secrets_scan` | url | скан страницы на утёкшие секреты (24 паттерна) | — ✅ |
| `ip_geo_asn` | ip | гео/ASN (ip-api) | — |
| `ip_ports` | ip | открытые порты/сервисы/CVE (Shodan InternetDB) | — ✅ |
| `ip_reputation` | ip | репутация/шум (GreyNoise Community) | — ✅ |
| `typosquat` | domain | look-alike домены + проверка регистрации (DNS) | — ✅ |
| `ioc` | ip/domain/url | репутация: VirusTotal + AbuseIPDB (IP) | VT/AbuseIPDB (free) |
| `domain_history` | domain | DNS/поддомены/NS (SecurityTrails) | SecurityTrails (free) |
| `crypto_address` | crypto | баланс/активность BTC (blockchain.info) и ETH (ethplorer) | — ✅ |
| `archive` | url | ближайший снимок Wayback (сохранение доказательств) | — ✅ |
| `email_gravatar` | email | Gravatar + пивот в домен | — |
| `email_mx` | email | MX/SPF/DMARC + детект одноразовых доменов (DNS) | — ✅ |
| `email_leaks` | email | HIBP (присутствие в утечках) | HIBP_API_KEY |
| `phone_info` | phone | оператор/регион/тип (офлайн phonenumbers) | — ✅ |
| `username_sweep` | username | чек ника со скорингом 0–100%; быстрый (21 платф. + WhatsMyName ~700) / deep (+ Maigret + Sherlock, дедуп, env `USERNAME_DEEP=1`) | — ✅ |
| `holehe_accounts` | email | email → ~120 сервисов (signup/reset-формы), in-process (не CLI) | — ✅ |

### Docker-only (реальные бинарники — недоступны на Vercel)

Запускают внешние инструменты через subprocess; без Docker сами определяют
отсутствие бинарника и отдают факт «недоступно», не падая. См. [DEPLOY.md](../DEPLOY.md).

| Энричер | Тип | Инструмент | Настройка |
|---------|-----|-----------|-----------|
| `theharvester` | domain | theHarvester (изолированный venv) | — |
| `subfinder` | domain | subfinder (статический бинарник) | — |
| `gitleaks_scan` | url (git-репо) | gitleaks (клон + скан истории) | — |
| `trufflehog_scan` | url (git-репо) | trufflehog (верификация активных секретов) | — |
| `blackbird` | username | Blackbird (изолированный venv) | — |
| `ghunt_email` | email | GHunt | **разовый `ghunt login`** |
| `amass` | domain | Amass (engine+enum+subs, клиент-серверный) | **`AMASS_ENABLE=1`** (выключен по умолчанию — минуты, не секунды) |

✅ = бесплатно, без ключа, работает «из коробки».

## Бэклог энричеров (по образцу каталога flowsint)

🇺🇦 **Украина:** `opendatabot` расширить (CourtService/PenaltyService/RealEstateService по ключу);
`youcontrol` (YouScore API, по ключу).
**Осталось:** `phone.carrier`, `domain.ssl/whois`.
✅ Реализованы keyless: `ip.ports` (Shodan InternetDB), `ip_reputation` (GreyNoise),
`typosquat` (свой генератор + DNS), `crypto_address` (BTC/ETH), `archive` (Wayback).
✅ Реализованы key-gated (graceful без ключа): `ioc` (VirusTotal + AbuseIPDB),
`domain_history` (SecurityTrails). Все ключи free-tier — см. `.env.example`.

> Принцип: пассивные источники по умолчанию; ключи и .env — вне репозитория;
> результаты складывай в `cases/<slug>/data/`. Полный список flowsint-энричеров как
> референс — [flowsint-integration.md](../knowledge/flowsint-integration.md).
