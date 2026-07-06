# Деплой Claude OSINT

Платформа упакована в один образ (multi-stage: Node собирает фронтенд, Python отдаёт
FastAPI). Подробности архитектуры — [web/ARCHITECTURE.md](web/ARCHITECTURE.md).

## Быстрый старт (Docker)

```bash
docker compose up -d --build
# открой http://localhost:8000  (редиректит на /app/)
```

Остановить: `docker compose down`. Логи: `docker compose logs -f`.

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

## Глубокий username-скан в контейнере

Датасет WhatsMyName (`scripts/wmn-data.json`) не входит в образ. Варианты:

```bash
# 1) выполнить внутри контейнера
docker compose exec osint python ../scripts/fetch_wmn.py
# 2) или смонтировать локальный файл — раскомментируй volume в docker-compose.yml
```
Включить режим: переменная окружения `USERNAME_DEEP=1`.

## Локальный запуск без Docker

```powershell
cd web
python -m pip install -r requirements.txt -r ..\scripts\requirements.txt
cd ui; npm install; npm run build; cd ..
python app.py            # http://127.0.0.1:8000
```
