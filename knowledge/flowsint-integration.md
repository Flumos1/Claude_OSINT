# Flowsint: анализ и интеграция

Оценка проекта [reconurge/flowsint](https://github.com/reconurge/flowsint) и того, как мы
используем его идеи. Дата анализа: 2026-06-10.

## Что это

Open-source граф-платформа для OSINT-расследований (self-hosted аналог Maltego):
строишь граф сущностей, автоматически обогащаешь узлы модулями-энричерами, визуализируешь связи.
Apache-2.0. Этический фреймворк совпадает с нашим (запрет слежки/доксинга/манипуляций).

**Стек:** Neo4j (граф) + PostgreSQL + Redis + FastAPI + Celery + React/TS, всё в Docker Compose.
**Модули:** flowsint-core (оркестратор, БД, vault, Celery), -types (Pydantic-модели),
-enrichers (логика обогащения), -api (FastAPI), -app (фронт).
**Энричеры:** домены (reverse DNS, поддомены, WHOIS, история, ASN), IP (гео, ASN, CIDR),
соцсети (Maigret), email (утечки, Gravatar, домены), крипто (транзакции, NFT),
сайты (краулинг, трекеры, текст), организации (ASN, владение доменами).

## Оценка ценности

**Сильнее нас:** автоматизация обогащения + граф в Neo4j + визуализация. То, что у нас
в плейбуках делается руками (pivoting, entities.md).

**Чего во flowsint нет (наш слой):** RU/СНГ-реестры (ЕГРЮЛ, kad.arbitr, ФССП), методология,
этика, ведение кейса и отчёты под заказчика, лёгкий старт.

**Минус:** тяжёлая инфраструктура (3 БД + Docker) — избыточна для разовых задач.

## Наша стратегия

**Б (сделано): архитектура энричеров.** Мы переняли модель flowsint-enrichers в `scripts/`:
единый контракт «сущность → граф (узлы/связи/факты с provenance)». См. ниже.

**А (на будущее): деплой платформы** — когда появится объёмный кейс и Docker.

## Контракт энричеров (`scripts/enrichers/`)

По мотивам flowsint-enrichers, но легковесно (чистый Python, без БД):

- `base.py` — `Node`, `Edge`, `Finding`, `EnricherResult`, декоратор `@enricher(name, type)`,
  реестр `REGISTRY`. Узлы/связи в граф-модели (Neo4j-friendly) — позже импортируемы во flowsint.
- Энричеры: `domain_enr` (RDAP/crt.sh/DNS/Wayback), `ip_enr` (гео/ASN), `email_enr`
  (Gravatar + пивот в домен), `ru_company_enr` (**наш дифференциатор**: валидация ИНН/ОГРН
  по контрольной сумме + deep-ссылки на реестры РФ).
- `enrich.py` — раннер: `python enrich.py <type> <value> [--json ...]`, собирает единый граф.

Добавить энричер: новый файл в `enrichers/`, функция `fn(value)->EnricherResult` с
`@enricher("имя","тип")`, импорт в `enrichers/__init__.py`. Бэклог: `breach_hibp` (по ключу),
`username_maigret`, `ioc_vt`, `crypto_wallet`, `ru_person` (ФССП/банкротство).

## Стратегия А — деплой flowsint (когда будет Docker)

> Требуется Docker Desktop (сейчас НЕ установлен). Это памятка на будущее, не выполнять сейчас.

1. Установить Docker Desktop для Windows (WSL2 backend).
2. `git clone https://github.com/reconurge/flowsint && cd flowsint`
3. Прочитать `README.md` и **`ETHICS.md`**; скопировать `.env`-пример, задать секреты/пароли БД.
4. `docker compose up -d` — поднимет Neo4j + Postgres + Redis + API + фронт.
5. Открыть UI на порту `5173` (единственный внешний; БД проксируются внутри).
6. Для внешнего доступа — reverse proxy с HTTPS (в репо пример Caddy). Не выставлять БД наружу.
7. Данные хранятся локально — подходит для чувствительных кейсов.
8. **Проверить перед доверием:** свежесть коммитов, issues, что секреты не в репо, обновления.

## Каталог энричеров flowsint (референс для нашего бэклога)

Из `flowsint-enrichers/` (имена = пивоты «X → Y»):

- **domain →** asn, ip, root_domain, subdomains, ssl, history, whois, whois_history, website, dehashed, dummy_individuals
- **ip →** asn, domain, ports, infos, fraudscore, dehashed
- **email →** domain(s), username, gravatar, leaks, hudsonrock, dehashed
- **phone →** carrier, infos, hudsonrock
- **social →** maigret, sherlock, hudsonrock, dehashed
- **organization →** asn, domains, infos · **individual →** domains, org
- **asn →** cidrs · **cidr →** ips · **crypto →** transactions, nfts
- **website →** crawler, links, subdomain, text, webtrackers · **n8n** коннектор

> У нас уже есть: domain (whois/subdomains/ip/wayback), ip (geo/asn), email (gravatar+domain).
> Приоритет добрать (см. scripts/README бэклог): ssl, whois_history, ip.ports (Shodan),
> username (maigret/sherlock), phone.carrier, email.leaks, crypto. `hudsonrock` (infostealer-логи)
> и `dehashed` — мощно, но dehashed платный и требует строгой этики (только свои/авторизованные).

### Как впишем в наш процесс (А)

- Сложный кейс (много сущностей) ведём граф во flowsint; экспорт находок → наш `cases/<slug>/`
  и финальный отчёт через `osint-report`.
- Наши RU-энричеры (ru_company и будущие) дополняют flowsint там, где у него пробел по РФ.
- `enrich.py --json` уже даёт граф-структуру (nodes/edges) — основа для импорта в Neo4j.
