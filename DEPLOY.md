# Деплой Claude OSINT

Платформа упакована в один образ (multi-stage: Node собирает фронтенд, Python отдаёт
FastAPI). Подробности архитектуры — [web/ARCHITECTURE.md](web/ARCHITECTURE.md).

## Быстрый старт (Docker)

```bash
docker compose up -d --build
# открой http://localhost:8000  (редиректит на /app/)
```

Остановить: `docker compose down`. Логи: `docker compose logs -f`.

## Авторизация

По умолчанию токен-авторизация **выключена** — годится только для localhost.
Для доступа из сети задай токен (включает защиту `/api/*` через cookie/заголовок):

```bash
# Linux/macOS
OSINT_TOKEN=$(openssl rand -hex 24) docker compose up -d --build
# или пропиши OSINT_TOKEN в .env рядом с docker-compose.yml
```

UI покажет страницу входа (`/login`), токен сохранится в httponly-cookie.
Программный доступ к API — заголовок `X-Token: <токен>`.

> ⚠️ Это один общий токен, не мульти-юзер. Полноценные аккаунты — следующий шаг
> (см. дорожную карту). Данные расследований чувствительны: наружу выставляй
> только за TLS reverse-proxy (Caddy/nginx) и с заданным токеном.

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
