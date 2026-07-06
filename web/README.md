# Claude OSINT — веб-платформа

Локальная веб-оболочка поверх движка энричеров. Строгий, читаемый интерфейс
(Inter + JetBrains Mono), светлая/тёмная темы. Объединяет лучшее у SpiderFoot
(чистый веб-воркфлоу), IntelOwl (дашборд/формы) и Maltego (граф связей).

## Возможности

- **Обзор** — статистика workspace, быстрый старт, карта энричеров.
- **Обогащение** — сущность → граф: факты с provenance и оценкой [A1..F6],
  интерактивный граф связей, таблица сущностей, сырой JSON.
- **Поиск ФЛ** — досье физлица: варианты имени, живой НАЗК, реестры UA/RU/межд., граф.
- **Recon-граф** — многошаговый пивотинг + корреляция (тиры CONFIRMED/PROBABLE/POSSIBLE),
  риск-флаги, таймлайн. Гейт правового основания — обязателен.
- **Спецобъекты** — вкладки: ✈ авиа- и ⚓ морской трекинг **активов** (не людей на борту),
  🛡 threat-IOC (VT/AbuseIPDB/GreyNoise).
- **Источники / Скилы / Кейсы** — реестры по странам, плейбуки, расследования из `cases/`.

**Экспорт и кейсы (на каждом результате):** отчёт в **MD / DOCX / PDF** (DOCX — на stdlib,
PDF — через печать браузера) и **💾 В кейс** — сохраняет JSON+MD в `cases/<slug>/data/`,
создаёт кейс из `_TEMPLATE` при отсутствии и дописывает `log.md`.

## Запуск

```powershell
cd "G:\Claude OSINT\web"
python -m pip install -r requirements.txt
python app.py                 # http://127.0.0.1:8000
$env:PORT=8123; python app.py # другой порт (HOST/PORT читаются из окружения)
```

Движок энричеров берётся из `../scripts` (нужны и его зависимости:
`pip install -r ..\scripts\requirements.txt`). API-докуменация: `/api/docs`.

## Новый фронтенд (React + Vite) — `ui/`

Идёт переход на современный стек (план: [ARCHITECTURE.md](ARCHITECTURE.md)).
Итерация 1 — умный поиск с авто-детектом типа и панелью **подсказок** «что дальше».

```powershell
cd web\ui
npm install
npm run dev          # дев-сервер Vite, проксирует /api на FastAPI (:8000)
# или сборка в production:
npm run build        # → web/static/dist; FastAPI отдаёт на /app/ (/ редиректит туда)
```

Для dev запусти параллельно бэкенд (`python app.py`). Старый SPA доступен на `/legacy`.

## Архитектура

- `app.py` — FastAPI: REST API (`/api/meta`, `/api/enrich[/report]`, `/api/person[/report]`,
  `/api/recon[/report]`, `/api/case/save`, `/api/sources/{code}`, `/api/skills`, `/api/cases`)
  + раздача статики. Переиспользует `scripts/` (enrich, person_recon, osint_graph, docx_lite).
- `static/` — `index.html` (структура), `styles.css` (дизайн-система), `app.js` (SPA).
- Граф — vis-network (CDN) с graceful-фолбэком на таблицы при отсутствии сети.

## Заметки

- Только локально (127.0.0.1). Наружу не выставлять без reverse-proxy и авторизации —
  интерфейс даёт доступ к данным расследований.
- Новые энричеры/страны подхватываются автоматически из движка и `knowledge/sources/`.
