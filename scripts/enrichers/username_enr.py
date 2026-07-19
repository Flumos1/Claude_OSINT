"""
Username-энричер (нейтральный) — проверка ника по платформам с оценкой уверенности.

РЕАЛЬНЫЙ автоматический сбор, а не ссылка на инструмент: программа сама прогоняет
ник через собственный движок проверки (HTTP + маркеры присутствия/отсутствия),
используя БАЗЫ САЙТОВ трёх открытых проектов (не их код/бинарники — subprocess/pipx
здесь не участвует, всё in-process):
  • WhatsMyName (WebBreacher, MIT) — scripts/wmn-data.json, ~700 сайтов;
  • Maigret (soxoj, MIT) — scripts/maigret-data.json, схема presenceStrs/absenceStrs;
  • Sherlock (sherlock-project, MIT) — scripts/sherlock-data.json, схема errorMsg
    (инвертирована: «нет маркера помилки» = профіль існує).
Все три файла закоммичены в репозиторий (бандлятся и на Vercel) — обновить:
`python scripts/fetch_wmn.py`, аналогично для maigret/sherlock (см. fetch_datasets.py).

Два режима:
  • быстрый (за замовчуванням) — 21 куратируемая платформа + WhatsMyName (до POOL_CAP),
    бюджет часу ~9с (безпечно під Vercel maxDuration, є запас на github_user поруч).
  • глибокий (USERNAME_DEEP=1 або окрема job-стрічка в UI) — той самий пул +
    Maigret + Sherlock (дедуп за доменом, до POOL_CAP), бюджет ~15с.
Обидва бюджети мають подвійний захист: жорсткий budget в as_completed() +
резервна перевірка time.monotonic() на кожній ітерації (на випадок, якщо перший
таймаут «попливе» під навантаженням) — ніколи не наближаємось до maxDuration.

Кожне влучення отримує score 0–100% і Admiralty-оцінку (буква D — джерело-скрейпер
ненадійне за природою; цифра рухається по нашій впевненості в самому детекті).
Скоринг ріже soft-404 (HTTP 200 на будь-який нік). Належність ніка все одно
підтверджуй вручну (аватар, перехресні посилання).
"""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeoutError
from urllib.parse import urlsplit

import requests

from .base import EnricherResult, enricher

TIMEOUT = float(os.getenv("USERNAME_DEEP_TIMEOUT", "5"))
# WORKERS=30 — емпірично перевірене стабільне значення. Більше воркерів (тестили 100)
# створює GIL-contention, через яку сам wall-clock дедлайн-контроль стає ненадійним
# (спостерігали перевищення бюджету вдвічі) — для serverless це неприпустимо.
WORKERS = int(os.getenv("USERNAME_DEEP_WORKERS", "30"))
UA = {"User-Agent": "Mozilla/5.0 (compatible; osint-username/2.0)"}

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WMN_PATH = os.path.join(_HERE, "wmn-data.json")
MAIGRET_PATH = os.path.join(_HERE, "maigret-data.json")
SHERLOCK_PATH = os.path.join(_HERE, "sherlock-data.json")

# Захисна стеля розміру пулу ПЕРЕД сабмітом у ThreadPoolExecutor. Емпірично: submit()
# 1700+ футур одразу створює overhead у as_completed()/wait(), через який wall-clock
# бюджет реально «пливе» (спостерігали 27с замість 20с) — сам submit тисяч futures
# дорогий незалежно від того, скільки з них реально встигне виконатись. При ≤900
# overhead мінімальний (перевірено: 20.2с при бюджеті 20.0с).
POOL_CAP = int(os.getenv("USERNAME_POOL_CAP", "500"))

# Wall-clock бюджет на весь прогін (серверлес-безпечно): fast укладається в
# maxDuration з запасом на github_user/накладні витрати; deep — окремий job-виклик,
# де username_sweep працює сам (без сусідів), тож бюджет ширший.
FAST_BUDGET = float(os.getenv("USERNAME_FAST_BUDGET", "9"))
DEEP_BUDGET = float(os.getenv("USERNAME_DEEP_BUDGET", "15"))

# (платформа, url-шаблон, текст-маркер «не найдено» при HTTP 200; None = чистый 404)
PLATFORMS = [
    ("GitHub", "https://github.com/{u}", None),
    ("GitLab", "https://gitlab.com/{u}", None),
    ("Reddit", "https://www.reddit.com/user/{u}/about.json", None),
    ("Keybase", "https://keybase.io/{u}", None),
    ("Dev.to", "https://dev.to/{u}", None),
    ("Replit", "https://replit.com/@{u}", None),
    ("Pastebin", "https://pastebin.com/u/{u}", None),
    ("Vimeo", "https://vimeo.com/{u}", None),
    ("About.me", "https://about.me/{u}", None),
    ("HackerNews", "https://news.ycombinator.com/user?id={u}", "No such user."),
    ("Steam", "https://steamcommunity.com/id/{u}", "The specified profile could not be found"),
    ("Telegram", "https://t.me/{u}", "tgme_page_title"),  # маркер ПРИСУТНОСТИ (інверсія нижче)
    ("Bitbucket", "https://bitbucket.org/{u}/", None),
    ("NPM", "https://www.npmjs.com/~{u}", None),
    ("PyPI", "https://pypi.org/user/{u}/", None),
    ("Codepen", "https://codepen.io/{u}", None),
    ("Last.fm", "https://www.last.fm/user/{u}", None),
    ("Medium", "https://medium.com/@{u}", None),
    ("SoundCloud", "https://soundcloud.com/{u}", None),
    ("Kaggle", "https://www.kaggle.com/{u}", None),
    ("Telegraph", "https://telegra.ph/{u}", None),
]


def _host(url: str) -> str:
    h = (urlsplit(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def _score(method: str, *, code_match: bool, redirected: bool, host_mismatch: bool):
    """
    Прозрачный аддитивный скоринг попадания. Возвращает (score 0..100, [причины]).
      method='present'  — найден маркер присутствия (e_string) → сильный сигнал;
      method='clean404' — вёттнутый curated-сайт даёт чистый 404 для несуществующих,
                          здесь HTTP 200 → надёжно (детектор различает);
      method='absent'   — HTTP 200 и НЕ найден маркер «не найдено» (m_string) → надёжно;
      method='code'     — только HTTP 200 без маркеров (WMN без e_string) → слабо, риск soft-404.
    Штрафы за признаки soft-404: редирект на чужой домен (login/главная) и редиректы вообще.
    """
    if method == "present":
        score, reasons = 80, ["маркер присутствия найден"]
    elif method == "clean404":
        score, reasons = 78, ["сайт даёт чистый 404 для несуществующих; здесь HTTP 200"]
    elif method == "absent":
        score, reasons = 70, ["HTTP 200 и нет маркера 'не найдено'"]
    else:
        score, reasons = 40, ["только HTTP 200 без маркера (риск soft-404)"]
    if code_match:
        score += 6
        reasons.append("код ответа ожидаемый")
    if host_mismatch:
        score -= 35
        reasons.append("редирект на другой домен (вероятен soft-404/login)")
    elif redirected:
        score -= 10
        reasons.append("был редирект")
    return max(0, min(100, score)), reasons


def _grade(score: int) -> str:
    """Admiralty: буква D (источник-скрейпер), цифра по уверенности в детекте."""
    if score >= 78:
        return "D3"
    if score >= 55:
        return "D4"
    return "D5"


def _get(url: str):
    return requests.get(url, headers=UA, timeout=TIMEOUT, allow_redirects=True)


def _check_curated(name: str, tpl: str, marker, u: str):
    url = tpl.format(u=u)
    try:
        r = _get(url)
    except Exception:
        return None  # таймаут/блокировка — тихо пропускаем
    code200 = r.status_code == 200
    if name == "Telegram":
        method, claimed = "present", code200 and (marker in r.text)
    elif marker:
        method, claimed = "absent", code200 and (marker not in r.text)
    else:
        method, claimed = "clean404", code200  # вёттнутый чистый 404 → 200 надёжно
    if not claimed:
        return None
    final = str(r.url)
    score, reasons = _score(
        method,
        code_match=code200,
        redirected=bool(r.history),
        host_mismatch=_host(final) != _host(url),
    )
    return {"platform": name, "url": url, "code": r.status_code, "score": score,
            "grade": _grade(score), "reasons": reasons, "category": ""}


def _check_wmn(site: dict, u: str):
    """Общий проверщик для нормализованных записей (WMN/Maigret/Sherlock — одна схема)."""
    tpl = site.get("uri_check") or ""
    if "{account}" not in tpl:
        return None
    url = tpl.replace("{account}", u)
    try:
        r = _get(url)
    except Exception:
        return None
    e_code = site.get("e_code", 200)
    e_string = site.get("e_string")
    m_string = site.get("m_string")
    body = r.text
    code_match = r.status_code == e_code
    if e_string:
        method = "present"
        claimed = code_match and (e_string in body)
        if claimed and m_string and m_string in body:
            claimed = False  # маркер «не найдено» перекрывает совпавший e_string
    elif m_string:
        # Инвертированная модель (Sherlock errorType=message): нет ошибки → профиль есть.
        method = "absent"
        claimed = code_match and (m_string not in body)
    else:
        method, claimed = "code", code_match
    if not claimed:
        return None
    final = str(r.url)
    score, reasons = _score(
        method,
        code_match=code_match,
        redirected=bool(r.history),
        host_mismatch=_host(final) != _host(url),
    )
    return {"platform": site.get("name", "?"), "url": url, "code": r.status_code,
            "score": score, "grade": _grade(score), "reasons": reasons,
            "category": site.get("cat", "")}


def _read_json(path: str):
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _load_wmn() -> list[dict]:
    """WhatsMyName → уже наша схема {name, uri_check(#{account}), e_code, e_string, m_string, cat}."""
    data = _read_json(WMN_PATH)
    if not data:
        return []
    out = []
    for s in data.get("sites", []):
        tpl = (s.get("uri_check") or "").replace("{account}", "{account}")
        if "{account}" not in tpl:
            continue
        out.append({"name": s.get("name", "?"), "uri_check": tpl,
                    "e_code": s.get("e_code", 200), "e_string": s.get("e_string"),
                    "m_string": s.get("m_string"), "cat": s.get("cat", "")})
    return out


def _load_maigret() -> list[dict]:
    """Maigret data.json → наша схема. checkType: message (presenseStrs/absenceStrs) или
    status_code (просто 200=есть). response_url и disabled — пропускаем (наш чекер не умеет)."""
    data = _read_json(MAIGRET_PATH)
    if not data:
        return []
    out = []
    for name, s in (data.get("sites") or {}).items():
        if s.get("disabled"):
            continue
        ctype = s.get("checkType")
        tpl = (s.get("url") or "").replace("{username}", "{account}")
        if "{account}" not in tpl:
            continue
        if ctype == "message":
            pres = s.get("presenseStrs") or []
            abs_ = s.get("absenceStrs") or []
            if not pres and not abs_:
                continue
            out.append({"name": name, "uri_check": tpl, "e_code": 200,
                        "e_string": pres[0] if pres else None,
                        "m_string": abs_[0] if abs_ else None,
                        "cat": ",".join(s.get("tags") or [])})
        elif ctype == "status_code":
            out.append({"name": name, "uri_check": tpl, "e_code": 200,
                        "e_string": None, "m_string": None,
                        "cat": ",".join(s.get("tags") or [])})
        # response_url и прочее — сознательно пропускаем (нужна логика сверки редиректа)
    return out


def _load_sherlock() -> list[dict]:
    """Sherlock data.json → наша схема. errorType: message (errorMsg = маркер ОТСУТСТВИЯ,
    инвертированная модель) или status_code (просто 200=есть). response_url — пропускаем."""
    data = _read_json(SHERLOCK_PATH)
    if not data:
        return []
    out = []
    for name, s in data.items():
        if name.startswith("$"):
            continue
        etype = s.get("errorType")
        tpl = (s.get("url") or "").replace("{}", "{account}")
        if "{account}" not in tpl:
            continue
        if etype == "message":
            em = s.get("errorMsg")
            m_string = em[0] if isinstance(em, list) and em else (em if isinstance(em, str) else None)
            if not m_string:
                continue
            out.append({"name": name, "uri_check": tpl, "e_code": 200,
                        "e_string": None, "m_string": m_string, "cat": ""})
        elif etype == "status_code":
            out.append({"name": name, "uri_check": tpl, "e_code": 200,
                        "e_string": None, "m_string": None, "cat": ""})
    return out


def _dedup_by_host(pools: list[list[dict]]) -> list[dict]:
    """Слить несколько пулов сайтов, убрав дубли по домену (приоритет — порядок пулов)."""
    seen: set[str] = set()
    out = []
    for pool in pools:
        for site in pool:
            h = _host(site["uri_check"].replace("{account}", "x"))
            if not h or h in seen:
                continue
            seen.add(h)
            out.append(site)
    return out


def _exclude_curated(sites: list[dict], curated_hosts: set[str]) -> list[dict]:
    return [s for s in sites if _host(s["uri_check"].replace("{account}", "x")) not in curated_hosts]


def _build_tasks(u: str, deep: bool):
    """Готовит список проверок. Возвращает (tasks, всего_сайтов, режим, note|None, budget)."""
    tasks = [("curated", _check_curated, p) for p in PLATFORMS]
    curated_hosts = {_host(tpl.format(u="x")) for _, tpl, _ in PLATFORMS}
    wmn = _exclude_curated(_load_wmn(), curated_hosts)

    if not deep:
        pool = _dedup_by_host([wmn])[:POOL_CAP]
        tasks += [("wmn", _check_wmn, s) for s in pool]
        total = len(PLATFORMS) + len(pool)
        mode = f"швидкий ({len(PLATFORMS)} куратируемых + WhatsMyName {len(pool)})"
        note = None if pool else ("wmn-data.json не знайдено — тільки куратируемий набір "
                                  "(запусти `python scripts/fetch_wmn.py`).")
        return tasks, total, mode, note, FAST_BUDGET

    maigret = _exclude_curated(_load_maigret(), curated_hosts)
    sherlock = _exclude_curated(_load_sherlock(), curated_hosts)
    full_pool = _dedup_by_host([wmn, maigret, sherlock])
    pool = full_pool[:POOL_CAP]
    tasks += [("wmn", _check_wmn, s) for s in pool]
    total = len(PLATFORMS) + len(pool)
    capped = len(full_pool) > POOL_CAP
    mode = (f"глибокий ({len(PLATFORMS)} куратируемих + WhatsMyName/Maigret/Sherlock, "
            f"{len(pool)}{f' з {len(full_pool)}' if capped else ''} після дедупу"
            f"{' і стелі бюджету' if capped else ''})")
    note = None
    if not (wmn or maigret or sherlock):
        note = ("Датасети не знайдені — тільки куратируемий набір. "
                "Запусти `python scripts/fetch_wmn.py` (та maigret/sherlock — див. README).")
    return tasks, total, mode, note, DEEP_BUDGET


def _submit(ex, tasks, u):
    futs = []
    for kind, fn, item in tasks:
        futs.append(ex.submit(fn, item[0], item[1], item[2], u) if kind == "curated"
                    else ex.submit(fn, item, u))
    return futs


def _run_pool(tasks, u: str, budget: float):
    """Выполняет проверки с жёстким wall-clock бюджетом (safe для serverless).

    as_completed(fs, timeout=budget) — единый таймаут на ВЕСЬ прогон (не на каждый
    futures, как concurrent.futures.wait в цикле — тот вариант при тысячах pending
    futures накапливает overhead и реально «плывёт» по времени). По истечении
    бюджета TimeoutError гасится, оставшиеся задачи отбрасываются при
    shutdown(wait=False) — не блокируем инвокейшен ожиданием фоновых потоков.
    Генератор yield-ит ('hit', dict) и ('progress', checked, total).
    """
    ex = ThreadPoolExecutor(max_workers=WORKERS)
    total = len(tasks)
    checked = 0
    # Резервна перевірка дедлайну (defense-in-depth): не покладаємось лише на
    # точність as_completed(timeout=budget) — під навантаженням вона «пливла»
    # (спостерігали перевищення на 30-40%). Явний time.monotonic()-чек після
    # кожного завершеного futures гарантує вихід незалежно від цього.
    deadline = time.monotonic() + budget
    try:
        futs = _submit(ex, tasks, u)
        try:
            for fut in as_completed(futs, timeout=budget):
                checked += 1
                try:
                    r = fut.result()
                except Exception:
                    r = None
                if r:
                    yield ("hit", r)
                if checked % 5 == 0 or checked == total:
                    yield ("progress", checked, total)
                if time.monotonic() >= deadline:
                    break
        except FuturesTimeoutError:
            pass  # бюджет вичерпано — повертаємо накопичене
        finally:
            yield ("progress", checked, total)
    finally:
        ex.shutdown(wait=False, cancel_futures=True)


def _assemble(value: str, u: str, hits: list, total: int, mode: str, deep: bool, note) -> EnricherResult:
    res = EnricherResult("username_sweep", "username", value)
    root = res.node("username", u)
    if note:
        res.fact(note, "username_sweep")
    hits.sort(key=lambda h: h["score"], reverse=True)
    high = sum(1 for h in hits if h["score"] >= 78)
    mid = sum(1 for h in hits if 55 <= h["score"] < 78)
    low = sum(1 for h in hits if h["score"] < 55)
    for h in hits:
        n = res.node("url", h["url"], platform=h["platform"], score=h["score"],
                     confidence=h["grade"], category=h["category"])
        res.edge(root, n, "profile_on")
        why = "; ".join(h["reasons"])
        res.fact(f"{h['platform']}: профіль існує ({h['score']}%, {h['grade']}) — {h['url']} [{why}]",
                 f"{h['platform']} (HTTP {h['code']})", h["grade"])
    res.fact(f"Режим: {mode}. Знайдено профілів: {len(hits)} із {total} у пулі "
             f"(висока впевненість ≥78%: {high}, середня 55–77%: {mid}, низька <55%: {low}). "
             f"Низьку — підтверджуй вручну (soft-404/блоки).", "username_sweep")
    if not deep:
        res.fact("Глибше (Maigret+Sherlock, дедуп): USERNAME_DEEP=1 або окрема "
                 "deep-перевірка в UI.", "username_sweep")
    return res


@enricher("username_sweep", "username")
def enrich_username(value: str) -> EnricherResult:
    u = value.strip().lstrip("@")
    deep = os.getenv("USERNAME_DEEP", "").lower() in ("1", "true", "yes")
    tasks, total, mode, note, budget = _build_tasks(u, deep)
    hits = []
    for kind, *rest in _run_pool(tasks, u, budget):
        if kind == "hit":
            hits.append(rest[0])
    return _assemble(value, u, hits, total, mode, deep, note)


def stream_username(value: str, deep: bool = True):
    """Генератор прогресса для асинхронных джоб (web/jobs.py).

    yield-ит события: {'event':'start',...}, ...'progress'..., и финальное
    {'event':'done','result': <граф в формате enrich.run>}.
    """
    u = value.strip().lstrip("@")
    tasks, total, mode, note, budget = _build_tasks(u, deep)
    hits = []
    yield {"event": "start", "total": total, "mode": mode}
    for kind, *rest in _run_pool(tasks, u, budget):
        if kind == "hit":
            hits.append(rest[0])
        elif kind == "progress":
            checked, tot = rest
            if checked % 10 == 0 or checked == tot:
                yield {"event": "progress", "checked": checked, "total": tot, "found": len(hits)}
    res = _assemble(value, u, hits, total, mode, deep, note)
    result = {
        "input": {"type": "username", "value": value, "country": None},
        "enrichers_run": ["username_sweep"],
        "nodes": [{"id": n.id, "type": n.type, "value": n.value, "attrs": n.attrs} for n in res.nodes],
        "edges": [{"source": e.source, "target": e.target, "rel": e.rel} for e in res.edges],
        "findings": [{"label": f.label, "text": f.text, "source": f.source, "confidence": f.confidence}
                     for f in res.findings],
    }
    yield {"event": "done", "result": result}
