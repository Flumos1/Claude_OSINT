# Журнал радара (обнаружение инструментов)

Лог прогонов радара (Trendshift / GitHub Trending / поиск по темам). Каждый прогон:
дата, находки, решение (взять / наблюдать / отклонить + причина). Радары — см.
[tools-catalog.md](tools-catalog.md) «Радары обнаружения инструментов».

---

## Прогон 2026-06-10

Источники: GitHub `topic:osint` + `created:>2025` (по звёздам), Trendshift тема web-scraping.

### ✅ Взять / завести к нам
| Репо | ★ | Лиц. | Чем полезно |
|------|---|------|-------------|
| [lissy93/web-check](https://github.com/lissy93/web-check) | 33k | MIT | All-in-one website OSINT (~30 проверок: DNS/SSL/headers/tech/cookies/DNSSEC). Дополняет `domain-infra`; идеи для энричеров домена. Self-host. |
| [kaifcodec/user-scanner](https://github.com/kaifcodec/user-scanner) | 2.1k | MIT | Email+Username, 205+ векторов (100+ email / 105+ username). Углубить наши `email_*`/`username_sweep`. |

### 👀 Наблюдать / изучить позже
| Репо | ★ | Лиц. | Заметка |
|------|---|------|---------|
| [simplifaisoul/osiris](https://github.com/simplifaisoul/osiris) | 5.1k | MIT | «OSINT-дашборд, Palantir-alt» — сравнение фич/дизайна для нашей веб-платформы. |
| [apurvsinghgautam/robin](https://github.com/apurvsinghgautam/robin) | 5.4k | MIT | AI Dark Web OSINT — для `threat-intel` (только наблюдение открытого, с осторожностью). |
| [elementalsouls/Claude-OSINT](https://github.com/elementalsouls/Claude-OSINT) | 1.6k | NOASSERTION | Парные Claude-скилы: 90+ recon-модулей, 48 secret-regex, 80+ dorks. Наша ниша — изучить паттерны дорков/регексов (лицензия неясна → не копировать код, только идеи). |
| social-analyzer, GHunt, phoneinfoga, maigret | — | — | Зрелые тулзы; уже в бэклоге энричеров (deeper username/phone/Google). |

### ❌ Отклонить (вне наших этических рамок)
| Репо/тип | Причина |
|----------|---------|
| `deanonymizer` (Trendshift) | Деанонимизация по стилю постинга — против [ethics-legal.md](ethics-legal.md). |
| `deepcloak` | Обход Cloudflare/DataDome/reCAPTCHA — нарушение ToS/анти-бот. |
| GhostTrack, Void-Tools, location/phone-трекеры | «Пробив»/слежка/трекинг локации — красные линии. |

### Решение
Завести в каталог: web-check, user-scanner. Кандидат на изучение в первую очередь —
**web-check** (идеи проверок домена для энричеров) и **elementalsouls/Claude-OSINT** (дорки/регексы).
