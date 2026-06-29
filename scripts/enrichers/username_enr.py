"""
Username-энричер (нейтральный) — проверка ника по платформам с оценкой уверенности.

Два режима:
  • быстрый (по умолчанию) — куратируемый набор из 21 платформы с надёжным 404;
  • глубокий (env USERNAME_DEEP=1) — датасет WhatsMyName (700+ сайтов, M. Hoffman),
    подтянуть его: `python scripts/fetch_wmn.py`. Проверка идёт параллельно.

Каждое попадание получает score 0–100% и Admiralty-оценку (буква D — источник-скрейпер
ненадёжен по природе; цифра 3/4/5 двигается по нашей уверенности в самом детекте).
Скоринг режет soft-404 (HTTP 200 на любой ник, редиректы на login/главную) — то, на чём
плоский «найдено/не найдено» спотыкается. Принадлежность ника всё равно подтверждай
вручную (аватар, перекрёстные ссылки): см. tools-catalog (maigret/whatsmyname глубже).
"""
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlsplit

import requests

from .base import EnricherResult, enricher

TIMEOUT = int(os.getenv("USERNAME_DEEP_TIMEOUT", "6"))
WORKERS = int(os.getenv("USERNAME_DEEP_WORKERS", "25"))
UA = {"User-Agent": "Mozilla/5.0 (compatible; osint-username/2.0)"}
WMN_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "wmn-data.json"))

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
    ("Telegram", "https://t.me/{u}", "tgme_page_title"),  # маркер ПРИСУТНОСТИ (инверсия ниже)
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
        score, reasons = 76, ["HTTP 200 и нет маркера 'не найдено'"]
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
        # подтверждение: маркер «не найдено» отсутствует
        if claimed and m_string and m_string in body:
            claimed = False
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


def _load_wmn():
    """Загрузить датасет WhatsMyName, опц. ограничить USERNAME_DEEP_MAX сайтами."""
    if not os.path.exists(WMN_PATH):
        return None
    try:
        with open(WMN_PATH, encoding="utf-8") as f:
            sites = json.load(f).get("sites", [])
    except Exception:
        return None
    cap = int(os.getenv("USERNAME_DEEP_MAX", "0"))
    return sites[:cap] if cap > 0 else sites


@enricher("username_sweep", "username")
def enrich_username(value: str) -> EnricherResult:
    res = EnricherResult("username_sweep", "username", value)
    u = value.strip().lstrip("@")
    root = res.node("username", u)

    deep = os.getenv("USERNAME_DEEP", "").lower() in ("1", "true", "yes")
    tasks = [("curated", _check_curated, p) for p in PLATFORMS]
    checked = len(PLATFORMS)
    mode = "быстрый (21 платформа)"

    if deep:
        sites = _load_wmn()
        if sites is None:
            res.fact("USERNAME_DEEP включён, но датасет не найден — запусти "
                     "`python scripts/fetch_wmn.py`. Работаю в быстром режиме.", "username_sweep")
        else:
            tasks += [("wmn", _check_wmn, s) for s in sites]
            checked += len(sites)
            mode = f"глубокий (WhatsMyName, {len(sites)} сайтов + 21 куратируемая)"

    hits = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = []
        for kind, fn, item in tasks:
            futs.append(ex.submit(fn, item[0], item[1], item[2], u) if kind == "curated"
                        else ex.submit(fn, item, u))
        for fut in as_completed(futs):
            try:
                r = fut.result()
            except Exception:
                r = None
            if r:
                hits.append(r)

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

    res.fact(f"Режим: {mode}. Знайдено профілів: {len(hits)} із {checked} перевірених "
             f"(висока впевненість ≥78%: {high}, середня 55–77%: {mid}, низька <55%: {low}). "
             f"Низьку — підтверджуй вручну (soft-404/блоки).", "username_sweep")
    if not deep:
        res.fact("Глибше: USERNAME_DEEP=1 + `python scripts/fetch_wmn.py` (700+ сайтів), "
                 "або maigret/whatsmyname/sherlock.", "tools-catalog")
    return res
