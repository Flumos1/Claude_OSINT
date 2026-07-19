# Деплой Claude OSINT

Платформа упакована в один образ (multi-stage: Node собирает фронтенд, Python отдаёт
FastAPI). Подробности архитектуры — [web/ARCHITECTURE.md](web/ARCHITECTURE.md).

## Быстрый старт (Docker)

```bash
docker compose up -d --build
# открой http://localhost:8000
```

Остановить: `docker compose down`. Логи: `docker compose logs -f`.

Сборка ставит и реальные OSINT-бинарники (не только код) — theHarvester, subfinder,
gitleaks, trufflehog, Blackbird, GHunt; они работают автоматически внутри enrich
(не требуют отдельных команд от оператора, кроме GHunt — см. ниже). Из-за скачивания
этих инструментов первая сборка образа занимает заметно дольше, чем просто Python+Node.

## Авторизация (мульти-юзер)

По умолчанию авторизация **выключена** — годится только для localhost. Для доступа
из сети включи мульти-юзер и засей администратора при первом запуске:

```bash
# .env рядом с docker-compose.yml:
OSINT_AUTH=1
OSINT_ADMIN_USER=admin
OSINT_ADMIN_PASSWORD=<надёжный-пароль>
```

Первый старт создаст админа. Вход — страница `/login` (логин+пароль), сессия в
httponly-cookie (7 дней). Админ добавляет пользователей (роли `admin`/`analyst`)
в разделе **«Пользователи»**. Пользователи и сессии — в SQLite `data/osint.db`
(том `./data`, в `.gitignore`).

Программный доступ к API: можно задать `OSINT_TOKEN` и слать заголовок
`X-Token: <токен>` (fallback для скриптов помимо пользовательских сессий).

> ⚠️ Данные расследований чувствительны: наружу выставляй **только** за TLS
> reverse-proxy и с включённой авторизацией.

## TLS reverse-proxy

Готовые примеры в [`deploy/`](deploy/): [Caddyfile](deploy/Caddyfile) (авто-TLS
Let's Encrypt) и [nginx.conf](deploy/nginx.conf). Оба проксируют на `127.0.0.1:8000`
и настроены под SSE (прогресс скана не буферизуется).

## Персистентность

`docker-compose.yml` монтирует `./cases` в контейнер — кейсы и собранные данные
(`cases/<slug>/data/collected.json`) переживают перезапуск.

## Глубокий username-скан

Датасеты WhatsMyName + Maigret + Sherlock уже закоммичены в репозиторий
(`scripts/{wmn,maigret,sherlock}-data.json`) — входят в образ автоматически,
ничего скачивать не нужно. Включить режим: переменная окружения `USERNAME_DEEP=1`
(или отдельная deep-кнопка в UI). Обновить датасеты: `python scripts/fetch_wmn.py`
(аналогично для maigret/sherlock — см. `scripts/README.md`).

## Docker-only инструменты (реальные бинарники, не заглушки)

Эти энричеры реально запускают внешние OSINT-инструменты через subprocess —
работают **только** при Docker-деплое (Vercel serverless не поддерживает
бинарники/shell). Без Docker энричер сам определяет отсутствие инструмента и
отдаёт факт «недоступно», не падая:

| Энричер | Инструмент | Тип входа | Настройка |
|---------|-----------|-----------|-----------|
| `theharvester` | theHarvester | domain | не нужна |
| `subfinder` | subfinder | domain | не нужна |
| `gitleaks_scan` | gitleaks | url (git-репо) | не нужна |
| `trufflehog_scan` | trufflehog | url (git-репо) | не нужна |
| `blackbird` | Blackbird | username | не нужна |
| `ghunt_email` | GHunt | email | **разовая ручная авторизация** |

### GHunt: разовая авторизация оператора

GHunt получає публічні дані Google-акаунту від імені **залогіненого акаунту
оператора** — автоматизувати цей крок не можна (і не варто: це були б чужі
облікові дані). Один раз після старту контейнера:

```bash
docker compose exec osint ghunt login
```
Вибери спосіб авторизації (розширення GHunt Companion або ручне введення куки —
**свій** Google-акаунт). Токен зберігається у volume `ghunt_creds` (переживає
`docker compose up --build`). Після цього `ghunt_email` в enrich працює автоматично.

## Локальный запуск без Docker

```powershell
cd web
python -m pip install -r requirements.txt -r ..\scripts\requirements.txt
cd ui; npm install; npm run build; cd ..
python app.py            # http://127.0.0.1:8000
```

---

# Деплой на Vercel (serverless) — полнофункционально

Приложение адаптировано под Vercel **без урезания**: React-фронтенд собирается и
раздаётся из CDN, FastAPI работает как ASGI-функция, а состояние (пользователи, сессии,
кейсы) хранится в **Upstash Redis (KV)**. Фоновые сканы стримятся инлайново (SSE в одном
запросе). Локальный Docker/Render при этом остаётся на SQLite/файлах — код **dual-mode**,
выбор автоматический по наличию KV-переменных.

### Что и почему
| Компонент | Локально/Docker | На Vercel |
|-----------|-----------------|-----------|
| Хранилище пользователей/сессий | SQLite `data/osint.db` | **Upstash Redis KV** |
| Кейсы (сохранённые результаты) | файлы `cases/<slug>/` | **Upstash Redis KV** |
| Фоновый deep-скан | очередь+поток | **инлайновый SSE** `/api/scan/stream` |
| Фронтенд | FastAPI отдаёт `/app/` | Vercel CDN отдаёт из корня |

Файлы деплоя (в репозитории): `vercel.json` (сборка Vite → `web/static/dist`, роутинг
`/api/*` → функция, SPA-fallback), `api/index.py` (ASGI-entry), корневой `requirements.txt`,
`.vercelignore`. `web/kv.py` — REST-клиент Upstash.

### Шаги
1. **GitHub** → пуш репозитория.
2. **Vercel → Add New → Project → Import**. Framework Preset: **Other** (всё задаёт `vercel.json`).
   Root Directory — корень репо.
3. **Storage → Upstash Redis** (в Vercel Marketplace, есть бесплатный тариф) → **Connect** к
   проекту. Он сам добавит env `KV_REST_API_URL` и `KV_REST_API_TOKEN` (или
   `UPSTASH_REDIS_REST_URL`/`_TOKEN` — код понимает оба).
4. **Environment Variables** (Settings → Environment Variables):
   | Переменная | Зачем | Обязательна |
   |------------|-------|-------------|
   | `OSINT_AUTH` = `1` | включить мульти-юзер авторизацию | **да, для публичного** |
   | `OSINT_ADMIN_USER`, `OSINT_ADMIN_PASSWORD` | сид первого админа (создаётся при первом старте) | **да** |
   | `VIRUSTOTAL_API_KEY`, `ABUSEIPDB_API_KEY`, `GREYNOISE_API_KEY`, `ODB_API_KEY`, `YOUCONTROL_API_KEY`, `HIBP_API_KEY`, `WHOISXML_API_KEY`, `OPENSANCTIONS_API_KEY`, `GITHUB_TOKEN` | живые данные энричеров (иначе keyless/deep-ссылки) | нет |

   `VERCEL=1` платформа ставит сама (включает secure-cookie).
5. **Deploy**. После сборки открой URL → страница `/login` (админ из env). Пользователей
   добавляешь в разделе **«Пользователи»**.

### Ограничения serverless (и как учтены)
- **Лимит времени функции** (~60 c Hobby / ~300 c Pro). Быстрый скан (~21–48 платформ) и
  обычные энричеры укладываются; **deep-скан** (сотни сайтов) на Hobby может обрезаться —
  используй Pro или обычный режим.
- **Без Upstash KV** приложение всё равно поднимется, но авторизация станет эфемерной
  (SQLite в `/tmp`, сбрасывается между холодными стартами), а сохранение кейсов вернёт
  ошибку. Для полноценной работы KV **обязателен** (шаг 3).
- Ключи API — только в Environment Variables Vercel, не в репозитории.
