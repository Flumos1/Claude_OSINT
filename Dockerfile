# Multi-stage: собрать React-фронтенд (Node), затем запустить FastAPI (Python).
# Контекст сборки — корень репозитория (нужны scripts/, knowledge/, cases/, web/).

FROM node:24-alpine AS ui
WORKDIR /ui
COPY web/ui/package*.json ./
RUN npm ci
COPY web/ui/ ./
# FastAPI раздаёт фронтенд под /app/ → базовый путь ассетов /app/. outDir=../static/dist.
ENV VITE_BASE=/app/
RUN npm run build

FROM python:3.12-slim AS app
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY scripts/requirements.txt scripts/requirements.txt
COPY web/requirements.txt web/requirements.txt
RUN pip install -r scripts/requirements.txt -r web/requirements.txt
COPY scripts/ scripts/
COPY web/ web/
COPY knowledge/ knowledge/
COPY cases/ cases/
# собранный фронтенд из первого слоя
COPY --from=ui /static/dist web/static/dist
WORKDIR /app/web
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
