"""
Username-энричер (нейтральный) — быстрая проверка ника по куратируемому набору платформ
с надёжным поведением 404. Бесплатно, без тяжёлых зависимостей (только requests).

Это лёгкий аналог Sherlock/Maigret для быстрого старта. Для глубокого охвата (сотни сайтов)
используй maigret/whatsmyname — см. tools-catalog. Низкая достоверность: возможны
soft-404 и блокировки; принадлежность ника подтверждай вручную (аватар, перекрёстные ссылки).
"""
import requests

from .base import EnricherResult, enricher

TIMEOUT = 8
UA = {"User-Agent": "Mozilla/5.0 (compatible; osint-username/1.0)"}

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


@enricher("username_sweep", "username")
def enrich_username(value: str) -> EnricherResult:
    res = EnricherResult("username_sweep", "username", value)
    u = value.strip().lstrip("@")
    root = res.node("username", u)
    found = 0

    for name, tpl, marker in PLATFORMS:
        url = tpl.format(u=u)
        try:
            r = requests.get(url, headers=UA, timeout=TIMEOUT, allow_redirects=True)
            claimed = None
            if name == "Telegram":
                claimed = r.status_code == 200 and (marker in r.text)
            elif marker:
                claimed = r.status_code == 200 and (marker not in r.text)
            else:
                claimed = r.status_code == 200
            if claimed:
                found += 1
                n = res.node("url", url, platform=name)
                res.edge(root, n, "profile_on")
                res.fact(f"{name}: профіль існує — {url}", f"{name} (HTTP {r.status_code})", "D4")
        except Exception:
            continue  # таймаут/блокування — пропускаємо тихо

    res.fact(f"Знайдено профілів: {found} із {len(PLATFORMS)} перевірених платформ. "
             f"Достовірність низька (можливі soft-404/блоки) — підтверджуй вручну.", "username_sweep")
    res.fact("Глибше: whatsmyname.app, maigret, sherlock (сотні сайтів).", "tools-catalog")
    return res
