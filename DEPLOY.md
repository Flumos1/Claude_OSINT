# Деплой на Vercel

Веб-оболочка (`web/app.py`, FastAPI) готова к деплою на Vercel как serverless ASGI-функция.

## Что работает на Vercel и что нет

✅ **Работает:** дашборд, обогащение (все энричеры), поиск ФЛ, recon-граф, спецобъекты
(aircraft/vessel/ioc), источники, скилы, экспорт отчётов **MD / DOCX / PDF**.

⚠️ **Ограничения serverless:**
- **Файловая система только для чтения** → «💾 Сохранить в кейс» **отключено** (кнопка скрыта,
  показан баннер демо-режима). Кейсы ведутся в локальном запуске. Env `VERCEL=1` ставится
  автоматически и включает read-only; можно форсить `READ_ONLY=1`.
- **Лимит времени запроса** (~10 c на Hobby, ~60 c на Pro): «медленные» энричеры
  (`username_sweep` по ~48 сайтам, `person_recon`, `domain_recon`) могут не успеть.
  На Pro-плане запас больше. Быстрые (company/ip/crypto/ioc/vessel/aircraft) — без проблем.

## Файлы деплоя (уже в репозитории)

- `vercel.json` — билд `api/index.py` через `@vercel/python`, роутинг всех путей в функцию,
  `includeFiles: "**"` (бандлит `web/`, `knowledge/`, `scripts/`, `.claude/`, `templates/`).
- `api/index.py` — ASGI-entry: добавляет пути и импортирует `app` из `web/app.py`.
- `requirements.txt` (корень) — зависимости для Vercel (fastapi, requests, dnspython,
  phonenumbers, python-dotenv, markdown).
- `.vercelignore` — исключает venv/кэш/данные кейсов/секреты.

## Шаги

1. **Залей репозиторий на GitHub** (если ещё нет).
2. **Vercel → Add New → Project → Import** этот репозиторий. Framework Preset: **Other**
   (vercel.json всё задаёт сам). Root Directory: **оставь корень репо**.
3. **Environment Variables** (Project Settings → Environment Variables):
   | Переменная | Зачем | Обязательна |
   |------------|-------|-------------|
   | `ACCESS_PASSWORD` | Пароль на вход (парольный гейт). Без неё доступ открыт всем. | **да, для публичного** |
   | `HIBP_API_KEY`, `VIRUSTOTAL_API_KEY`, `ABUSEIPDB_API_KEY`, `GREYNOISE_API_KEY`, `ODB_API_KEY`, `YOUCONTROL_API_KEY`, `WHOISXML_API_KEY`, `OPENSANCTIONS_API_KEY` | Живые данные соответствующих энричеров (иначе — keyless/deep-ссылки). | нет |

   `VERCEL=1` платформа ставит сама — read-only включится автоматически.
4. **Deploy**. После билда открой URL — при заданном `ACCESS_PASSWORD` появится экран входа.

## Обновление после изменений

`git push` в подключённую ветку → Vercel пересоберёт автоматически.

## Заметки по безопасности

- Публичный OSINT-инструмент без защиты противоречит OPSEC-рамкам ([knowledge/opsec.md](knowledge/opsec.md)) —
  **задай `ACCESS_PASSWORD`**. Cookie-сессия подписана (HMAC), `Secure`+`HttpOnly` на HTTPS.
- API-ключи держи только в Environment Variables Vercel (не в репозитории).
- Для чувствительных расследований (запись кейсов, тяжёлые прогоны) используй **локальный**
  запуск: `cd web && python app.py`.
