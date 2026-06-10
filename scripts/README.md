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

```powershell
python domain_recon.py example.com --json ..\cases\<slug>\data\example.com.json
```

## Что добавить дальше (бэклог)

- `breach_check.py` — HIBP по email/домену (свои/авторизованные данные).
- `ioc_lookup.py` — VirusTotal/AbuseIPDB/GreyNoise по IP/домену/хешу.
- `username_sweep.py` — обёртка над whatsmyname/Sherlock-списком.
- `sanctions_check.py` — поиск по OpenSanctions API.
- `typosquat_gen.py` — генерация и проверка доменов-двойников (dnstwist-логика).
- `archive_page.py` — Playwright: скриншот + PDF + Wayback Save для доказательств.

> Принцип: пассивные источники по умолчанию; ключи и .env — вне репозитория;
> результаты складывай в `cases/<slug>/data/`.
