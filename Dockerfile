# Multi-stage: собрать React-фронтенд (Node), затем запустить FastAPI (Python)
# + вшить реальные OSINT-бинарники (theHarvester, subfinder, gitleaks, trufflehog,
# Blackbird, GHunt, Amass) — доступны ТОЛЬКО в Docker-образе (Vercel serverless их
# не поддерживает: нет shell/read-only FS). Контекст сборки — корень репозитория.

FROM node:24-alpine AS ui
WORKDIR /ui
COPY web/ui/package*.json ./
RUN npm ci
COPY web/ui/ ./
# app.py монтирует dist в КОРЕНЬ (см. web/app.py) — base остаётся дефолтным "/".
# outDir=../static/dist (см. vite.config.ts). /app и /app/ — редирект на / для совместимости.
RUN npm run build

FROM python:3.12-slim AS tools
# Отдельный слой для инструментов — тяжёлые скачивания/клоны кэшируются независимо
# от изменений в scripts/web (не инвалидируются каждым git-коммитом кода).
RUN apt-get update && apt-get install -y --no-install-recommends \
      git curl ca-certificates unzip tar pipx \
    && rm -rf /var/lib/apt/lists/*

# --- Go-бинарники (статические, с GitHub Releases; архитектура amd64/arm64) ---
RUN set -eu; \
    case "$(dpkg --print-architecture)" in \
      amd64) SF_ARCH=amd64; GL_ARCH=x64; TH_ARCH=amd64; AM_ARCH=amd64 ;; \
      arm64) SF_ARCH=arm64; GL_ARCH=arm64; TH_ARCH=arm64; AM_ARCH=arm64 ;; \
      *) echo "unsupported arch"; exit 1 ;; \
    esac; \
    curl -sSfL "https://github.com/projectdiscovery/subfinder/releases/latest/download/subfinder_$(curl -sSfL https://api.github.com/repos/projectdiscovery/subfinder/releases/latest | grep -oP '"tag_name":\s*"v\K[^"]+')_linux_${SF_ARCH}.zip" -o /tmp/subfinder.zip \
      && unzip -q /tmp/subfinder.zip -d /usr/local/bin subfinder && chmod +x /usr/local/bin/subfinder && rm /tmp/subfinder.zip; \
    curl -sSfL "https://github.com/gitleaks/gitleaks/releases/latest/download/gitleaks_$(curl -sSfL https://api.github.com/repos/gitleaks/gitleaks/releases/latest | grep -oP '"tag_name":\s*"v\K[^"]+')_linux_${GL_ARCH}.tar.gz" -o /tmp/gitleaks.tgz \
      && tar -xzf /tmp/gitleaks.tgz -C /usr/local/bin gitleaks && chmod +x /usr/local/bin/gitleaks && rm /tmp/gitleaks.tgz; \
    curl -sSfL "https://github.com/trufflesecurity/trufflehog/releases/latest/download/trufflehog_$(curl -sSfL https://api.github.com/repos/trufflesecurity/trufflehog/releases/latest | grep -oP '"tag_name":\s*"v\K[^"]+')_linux_${TH_ARCH}.tar.gz" -o /tmp/trufflehog.tgz \
      && tar -xzf /tmp/trufflehog.tgz -C /usr/local/bin trufflehog && chmod +x /usr/local/bin/trufflehog && rm /tmp/trufflehog.tgz; \
    mkdir -p /opt/amass \
      && curl -sSfL "https://github.com/owasp-amass/amass/releases/latest/download/amass_linux_${AM_ARCH}.tar.gz" -o /tmp/amass.tgz \
      && tar -xzf /tmp/amass.tgz -C /opt/amass --strip-components=1 \
      && chmod +x /opt/amass/amass && rm /tmp/amass.tgz

# --- theHarvester (изолированный venv — пинованные fastapi/uvicorn конфликтуют
#     с нашим web/requirements.txt, поэтому НЕ в общее окружение) ---
RUN git clone --depth 1 https://github.com/laramies/theHarvester /opt/theharvester \
    && python3 -m venv /opt/theharvester-venv \
    && /opt/theharvester-venv/bin/pip install --no-cache-dir /opt/theharvester \
    && rm -rf /opt/theharvester/.git

# --- Blackbird (изолированный venv — своя версия зависимостей) ---
RUN git clone --depth 1 https://github.com/p1ngul1n0/blackbird /opt/blackbird \
    && python3 -m venv /opt/blackbird/.venv \
    && /opt/blackbird/.venv/bin/pip install --no-cache-dir -r /opt/blackbird/requirements.txt \
    && rm -rf /opt/blackbird/.git

# --- GHunt (pipx сам создаёт изолированный venv) ---
ENV PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin
RUN pipx install ghunt

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

# Реальные бинарники + изолированные venvs из слоя tools (theHarvester/subfinder/
# gitleaks/trufflehog/Blackbird/GHunt/Amass) — делают Docker-only энричеры
# (scripts/enrichers/theharvester_enr.py, subfinder_enr.py, gitleaks_enr.py,
# trufflehog_enr.py, blackbird_enr.py, ghunt_enr.py, amass_enr.py) реально рабочими.
# На Vercel этих файлов нет — энричеры сами определяют отсутствие бинарника и
# мягко деградируют (не ошибка). Amass дополнительно выключен по умолчанию
# (AMASS_ENABLE=1 чтобы включить) — клиент-серверный скан на минуты, не секунды.
COPY --from=tools /usr/local/bin/subfinder /usr/local/bin/subfinder
COPY --from=tools /usr/local/bin/gitleaks /usr/local/bin/gitleaks
COPY --from=tools /usr/local/bin/trufflehog /usr/local/bin/trufflehog
COPY --from=tools /usr/local/bin/ghunt /usr/local/bin/ghunt
COPY --from=tools /opt/pipx /opt/pipx
COPY --from=tools /opt/theharvester-venv /opt/theharvester-venv
COPY --from=tools /opt/blackbird /opt/blackbird
COPY --from=tools /opt/amass /opt/amass
ENV THEHARVESTER_BIN=/opt/theharvester-venv/bin/theHarvester
ENV BLACKBIRD_DIR=/opt/blackbird
ENV BLACKBIRD_PYTHON=/opt/blackbird/.venv/bin/python
ENV AMASS_BIN=/opt/amass/amass
# git нужен gitleaks_enr.py для клонирования репозитория перед сканом
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/web
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
