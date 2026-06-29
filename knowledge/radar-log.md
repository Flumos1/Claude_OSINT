# Журнал радара (обнаружение инструментов)

Лог прогонов радара (Trendshift / GitHub Trending / поиск по темам). Каждый прогон:
дата, находки, решение (взять / наблюдать / отклонить + причина). Радары — см.
[tools-catalog.md](tools-catalog.md) «Радары обнаружения инструментов».

---

## Прогон 2026-06-29

Источник: Telegram-канал DevHub (анонс тулзы) + веб-сверка с альтернативами по username-OSINT.

### 👀 Наблюдать / завести как внешний инструмент
| Репо | Чем полезно | Решение |
|------|-------------|---------|
| [arxhr007/Aliens_eye](https://github.com/arxhr007/Aliens_eye) | 840+ аккаунтов, AI-детекция + confidence score 0–100% (v2.0, июнь 2026). Фишка — скоринг уверенности, которого нет у Maigret. | В каталог (ники). Confidence-скоринг — идея для `username_sweep` (ранжировать хиты, резать ложные). |
| [webbreacher/whatsmyname](https://github.com/webbreacher/whatsmyname) | 700+ платформ, open-source JSON-датасет (M. Hoffman) — детект-основа многих тулз; веб-версии без установки. | В каталог. Датасет — кандидат как источник правил для `username_sweep`. |
| [p1ngul1n0/blackbird](https://github.com/p1ngul1n0/blackbird) | Username по 600+ сайтам, современный UI/JSON. | В каталог как альтернатива Sherlock/Maigret. |

> ⚠️ Подача в Telegram («пробиваем ЛЮБОГО», «без ограничений») — маркетинг в серой зоне.
> Сами инструменты работают только по публичным данным; применять — строго в рамках
> [ethics-legal.md](ethics-legal.md) (KYC/DD/CTF/пентест с основанием), без слежки за частными лицами.

### Решение (2026-06-29)
Добавлены в [tools-catalog.md](tools-catalog.md) «Люди / ники». Заметка по Maigret обновлена
актуальными данными (v0.5, 3100+ сайтов, рекурсия). Идею confidence-скоринга — в бэклог `username_sweep`.

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

### Решение — ВНЕДРЕНО (2026-06-10)
Ценность находок перенесена к нам (не ссылки, а рабочий код):
- **web-check** → энричер `website` (SSL/security-заголовки/сервер/robots/security.txt, оценка A–F).
- **elementalsouls/Claude-OSINT** (дорки/регексы) → `dorks.py` (Google/Bing/Yandex дорки для
  домена и персоны, интегрированы в `domain`/person_search) + `secrets_scan.py` (24 secret-regex,
  скан URL/файла) + энричер `secrets_scan` (тип url).
- **user-scanner** → расширен список платформ `username_sweep` (12→21).
web-check и user-scanner также в tools-catalog как внешние инструменты.
