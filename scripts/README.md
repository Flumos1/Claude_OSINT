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
python enrich.py company 7707083893     # валидация ИНН/ОГРН + ссылки на реестры РФ
python enrich.py ip 8.8.8.8
python enrich.py email user@example.com
```

## Архитектура энричеров

`enrichers/` — модули по контракту «сущность → граф», по мотивам flowsint
(см. [knowledge/flowsint-integration.md](../knowledge/flowsint-integration.md)).
Граф-вывод (nodes/edges) совместим с Neo4j — позже импортируем во flowsint.
Добавить энричер: файл в `enrichers/`, функция `fn(value)->EnricherResult` с
`@enricher("имя","тип")`, импорт в `enrichers/__init__.py`.

## Что добавить дальше (бэклог)

- `breach_check.py` — HIBP по email/домену (свои/авторизованные данные).
- `ioc_lookup.py` — VirusTotal/AbuseIPDB/GreyNoise по IP/домену/хешу.
- `username_sweep.py` — обёртка над whatsmyname/Sherlock-списком.
- `sanctions_check.py` — поиск по OpenSanctions API.
- `typosquat_gen.py` — генерация и проверка доменов-двойников (dnstwist-логика).
- `archive_page.py` — Playwright: скриншот + PDF + Wayback Save для доказательств.

> Принцип: пассивные источники по умолчанию; ключи и .env — вне репозитория;
> результаты складывай в `cases/<slug>/data/`.
