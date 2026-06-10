# Claude OSINT Workspace

Рабочее пространство для OSINT с Claude Code: корпоративный due diligence, threat
intelligence, расследования/фактчекинг и обучение методологии. Регион — RU/СНГ + международный.

> ⚖️ Только легальный и этичный OSINT по открытым источникам. Рамки —
> [knowledge/ethics-legal.md](knowledge/ethics-legal.md). Без слежки за частными лицами,
> доксинга и обхода авторизации.

## Структура

| Папка | Что внутри |
|-------|-----------|
| [CLAUDE.md](CLAUDE.md) | Инструкция проекта для Claude (читается каждой сессией) |
| `.claude/skills/` | Скилы-плейбуки: orchestrator, company-dd, person-osint, domain-infra, threat-intel, osint-report |
| `knowledge/` | Методология, каталоги источников (RU+intl), инструменты, этика, OPSEC |
| `templates/` | Шаблоны отчётов и брифов |
| `scripts/` | Утилиты автоматизации + движок энричеров (Python) |
| [`web/`](web/) | Веб-платформа (FastAPI): дашборд, обогащение с графом, источники, скилы, кейсы |
| `cases/` | Расследования; `_TEMPLATE` — структура нового кейса |
| `data/` | Сырые выгрузки (вне репозитория) |

## Быстрый старт

1. Опиши задачу Claude: *«проверь компанию X»*, *«разведка по домену Y»*, *«проверь утечки по нашему домену»*.
2. Claude через скил **osint-orchestrator** уточнит цель/основание, заведёт кейс в `cases/`
   и направит к нужному плейбуку.
3. По завершении — отчёт через **osint-report** (в Markdown / DOCX / PDF).

### Веб-платформа

```powershell
cd web
python -m pip install -r requirements.txt
python app.py     # http://127.0.0.1:8000
```

Строгий интерфейс: запуск энричеров с графом связей, источники по странам (🇺🇦 приоритет),
скилы и кейсы. Подробнее — [web/README.md](web/README.md).

## Скилы (когда что)

| Объект | Скил |
|--------|------|
| Компания, контрагент, бенефициары | `company-dd` |
| Человек (с основанием) | `person-osint` |
| Домен, сайт, IP, инфраструктура | `domain-infra` |
| Утечки, фишинг, IOC, бренд | `threat-intel` |
| Любой / несколько | `osint-orchestrator` → маршрутизация |
| Финальный отчёт | `osint-report` |

## База знаний

- [methodology.md](knowledge/methodology.md) — цикл разведки, pivoting, оценка достоверности, верификация
- [sources/](knowledge/sources/) — источники по странам: **[🇺🇦 ua.md](knowledge/sources/ua.md) (приоритет)**, [🇷🇺 ru.md](knowledge/sources/ru.md), [🌍 intl.md](knowledge/sources/intl.md), [шаблон новой страны](knowledge/sources/_country-template.md)
- [tools-catalog.md](knowledge/tools-catalog.md) — инструменты
- [ethics-legal.md](knowledge/ethics-legal.md) — этика и право
- [opsec.md](knowledge/opsec.md) — OPSEC исследователя
