# Каталог инструментов

> Установка по необходимости. Многие — CLI на Python. Часть требует API-ключей.
> Перед использованием — проверь легальность и ToS целевого ресурса.

> 📚 **Полный индекс 1400+ инструментов:** [tools-index.md](tools-index.md) — автогенерация
> из [`jivoi/awesome-osint`](https://github.com/jivoi/awesome-osint) скриптом
> `scripts/fetch_awesome_osint.py` (обновляется по запросу). Поиск по индексу:
> `python scripts/fetch_awesome_osint.py --search <term>`.
> Витрина того же источника онлайн: [OSINT Brasil / osint-explorer](https://github.com/azurejoga/osint-explorer).
> ⚠️ Индекс импортирован «как есть» — фильтруй через [ethics-legal.md](ethics-legal.md).
> Ниже — отобранный нами короткий список рабочих лошадок.

## Радары обнаружения инструментов (скаут нового)

> Не источники данных о объектах, а способ **рано находить новые OSINT/recon/scraping-инструменты**
> (как мы нашли flowsint). Просматривать периодически (раз в ~2 недели); стоящее — оценивать
> и заводить к нам (энричер/ссылка). Шумно — фильтруй под OSINT.

| Радар | Что даёт | Как смотреть |
|-------|----------|--------------|
| [Trendshift](https://trendshift.io/) | Трендовые GitHub-репо в реальном времени по импульсу роста | Темы **web scraping**, **security**, **AI-agents**; срезы день/неделя |
| GitHub Trending | Официальный тренд | github.com/trending, фильтр по языку/теме |
| [awesome-osint](https://github.com/jivoi/awesome-osint) | Curated-список (полнота) | наш `tools-index.md` — зеркало |

## Фреймворки и наборы

| Инструмент | Назначение | Заметка |
|-----------|-----------|---------|
| Maltego | Граф-разведка, трансформы | GUI, есть free (Community) |
| flowsint | Open-source граф-платформа (self-host Maltego) | Apache-2.0, Docker; см. [flowsint-integration.md](flowsint-integration.md) |
| SpiderFoot | Автоматизированный OSINT-скан по 200+ модулям | self-host, веб-UI |
| recon-ng | Модульный recon-фреймворк | CLI, как metasploit для OSINT |
| theHarvester | Сбор email/поддоменов/хостов по домену | быстрый старт по компании |
| OSINT Framework | osintframework.com — каталог-дерево ресурсов | навигатор, не инструмент |

## Домены / инфраструктура

| Инструмент | Назначение |
|-----------|-----------|
| web-check (lissy93) | All-in-one website OSINT: ~30 проверок (DNS/SSL/headers/tech/cookies) | MIT, self-host; радар 2026-06 |
| amass | Перечисление поддоменов (OWASP), активное+пассивное |
| subfinder | Быстрый пассивный subdomain enum |
| dnsx / dnsrecon | DNS-резолв, типы записей, зоны |
| httpx | Пробинг живых хостов, заголовки, тех-стек |
| whois / RDAP client | Регистрационные данные |
| Shodan CLI | Поиск по shodan из терминала |

## Люди / ники / почты / телефоны

| Инструмент | Назначение |
|-----------|-----------|
| Maigret | **Топ класса:** username по 3100+ сайтам (v0.5), рекурсивный поиск связанных аккаунтов, отчёты HTML/PDF/XMind/Markdown |
| Sherlock | Username по 400+ сайтам; лёгкий, скриптуется, CSV/XLSX, прокси/Tor |
| WhatsMyName ([webbreacher](https://github.com/webbreacher/whatsmyname)) | 700+ платформ; open-source JSON-датасет (M. Hoffman) — детект-основа многих тулз; есть веб-версии без установки |
| Aliens Eye ([arxhr007](https://github.com/arxhr007/Aliens_eye)) | 840+ аккаунтов, AI-детекция + confidence score 0–100% (v2.0, радар 2026-06) |
| Blackbird ([p1ngul1n0](https://github.com/p1ngul1n0/blackbird)) | Username по 600+ сайтам, современный UI/JSON-отчёты |
| user-scanner (kaifcodec) | Email+Username, 205+ векторов (MIT; радар 2026-06) |
| Holehe | Проверка, где зарегистрирован email (по «забыли пароль»), 120+ сервисов |
| PhoneInfoga | Разведка по телефону |
| GHunt | Разведка по Google-аккаунту/Gmail |

## Соцсети

| Инструмент | Назначение |
|-----------|-----------|
| snscrape | Сбор постов из соцсетей без API |
| Instaloader | Публичные данные Instagram |
| twscrape | Сбор из X/Twitter |
| TgStat / Telemetr | Аналитика Telegram-каналов (веб) |

## Изображения / гео

| Инструмент | Назначение |
|-----------|-----------|
| ExifTool | Чтение/анализ метаданных медиа |
| SunCalc / suncalc.org | Положение солнца → хронолокация по теням |
| Overpass Turbo | Запросы к OpenStreetMap по объектам на местности |
| Google Earth Pro | Историч. спутник, измерения, 3D |

## Утечки / секреты / код

| Инструмент | Назначение |
|-----------|-----------|
| gitleaks / trufflehog | Поиск секретов в git-репозиториях |
| h8mail | Поиск email в утечках (с API) |
| github-search dorks | Поиск ключей/почт в публичном коде |

## Архивация / сохранение доказательств

| Инструмент | Назначение |
|-----------|-----------|
| ArchiveBox | Self-host архив страниц (HTML, PDF, screenshot, WARC) |
| SingleFile (расширение) | Сохранение страницы в один HTML |
| Wayback «Save Page Now» | Публичный архив на момент сбора |
| wkhtmltopdf / Playwright | Скриншоты/PDF страниц из скрипта |
| hashdeep / sha256sum | Хеши файлов-доказательств для целостности |

## Что доступно прямо сейчас в этом workspace

- **WebSearch / WebFetch** (инструменты Claude) — поиск и чтение страниц.
- **Claude-in-Chrome** — управляемый браузер для интерактивных сайтов/реестров.
- **Python + PowerShell** — для скриптов в `scripts/`.
- Скилы `anthropic-skills:pdf / docx / xlsx` — для выгрузок и отчётов.

> Совет: не ставь весь зоопарк сразу. Под конкретный кейс — нужный инструмент.
> Базовый старт по компании: реестр + Checko/Rusprofile + kad.arbitr + fssp.
> Базовый старт по домену: RDAP + crt.sh + Wayback + urlscan + VirusTotal.
