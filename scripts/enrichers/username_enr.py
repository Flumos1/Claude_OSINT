"""
Username-энричер (нейтральный) — проверка ника по куратируемому набору платформ
с надёжным поведением 404. Бесплатно, без тяжёлых зависимостей (только requests).

Два режима:
1. Курируемый список ~60 платформ по категориям (быстрый старт, маркерная детекция).
2. Опционально — датасет WhatsMyName (`scripts/data/wmn-data.json`): если файл присутствует,
   прогоняем сотни сайтов поверх курируемого (maigret/whatsmyname-уровень, keyless, без вендоринга).
   Файла нет → тихо работаем только на курируемом списке. Скачать:
   https://raw.githubusercontent.com/WebBreacher/WhatsMyName/main/wmn-data.json

Низкая достоверность: возможны soft-404 и блокировки; принадлежность ника подтверждай
вручную (аватар, перекрёстные ссылки).
"""
import json
import os

import requests

from .base import EnricherResult, enricher

TIMEOUT = 8
UA = {"User-Agent": "Mozilla/5.0 (compatible; osint-username/1.0)"}
WMN_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "wmn-data.json"
)
WMN_CAP = 400  # предохранитель: сколько сайтов из WMN максимум проверять за прогон

# (категория, платформа, url-шаблон, маркер). marker:
#   None        — профиль есть, если HTTP 200 (чистый 404 на отсутствии);
#   "...text"   — профиль есть, если 200 И текста-«не найдено» НЕТ;
#   "+...text"  — инверсия: профиль есть, если 200 И текст-маркер ПРИСУТНИЯ ЕСТЬ.
PLATFORMS = [
    # — Разработка / код —
    ("dev", "GitHub", "https://github.com/{u}", None),
    ("dev", "GitLab", "https://gitlab.com/{u}", None),
    ("dev", "Bitbucket", "https://bitbucket.org/{u}/", None),
    ("dev", "Keybase", "https://keybase.io/{u}", None),
    ("dev", "Dev.to", "https://dev.to/{u}", None),
    ("dev", "NPM", "https://www.npmjs.com/~{u}", None),
    ("dev", "Codepen", "https://codepen.io/{u}", None),
    ("dev", "Kaggle", "https://www.kaggle.com/{u}", None),
    ("dev", "DockerHub", "https://hub.docker.com/u/{u}", None),
    ("dev", "Habr", "https://habr.com/ru/users/{u}/", None),
    # — Форумы / Q&A —
    ("forum", "HackerNews", "https://news.ycombinator.com/user?id={u}", "No such user."),
    ("forum", "StackOverflow", "https://stackoverflow.com/users/{u}", None),
    ("forum", "Reddit", "https://www.reddit.com/user/{u}/about.json", None),
    ("forum", "Pikabu", "https://pikabu.ru/@{u}", None),
    ("forum", "Disqus", "https://disqus.com/by/{u}/", None),
    ("forum", "Telegraph", "https://telegra.ph/{u}", None),
    ("forum", "Pastebin", "https://pastebin.com/u/{u}", None),
    # — Соцсети / медиа —
    ("social", "Telegram", "https://t.me/{u}", "+tgme_page_title"),
    ("social", "VK", "https://vk.com/{u}", None),
    ("social", "OK", "https://ok.ru/{u}", None),
    ("social", "Mastodon (mastodon.social)", "https://mastodon.social/@{u}", None),
    ("social", "About.me", "https://about.me/{u}", None),
    ("social", "Linktree", "https://linktr.ee/{u}", None),
    ("social", "Gravatar", "https://gravatar.com/{u}", None),
    # — Творчество / фото / видео —
    ("creative", "Behance", "https://www.behance.net/{u}", None),
    ("creative", "Dribbble", "https://dribbble.com/{u}", None),
    ("creative", "DeviantArt", "https://www.deviantart.com/{u}", None),
    ("creative", "Flickr", "https://www.flickr.com/people/{u}", None),
    ("creative", "Vimeo", "https://vimeo.com/{u}", None),
    ("creative", "SoundCloud", "https://soundcloud.com/{u}", None),
    ("creative", "Last.fm", "https://www.last.fm/user/{u}", None),
    ("creative", "Bandcamp", "https://{u}.bandcamp.com", None),
    # — Гейминг / стримы —
    ("gaming", "Steam", "https://steamcommunity.com/id/{u}", "The specified profile could not be found"),
    ("gaming", "itch.io", "https://{u}.itch.io", None),
    ("gaming", "Roblox", "https://www.roblox.com/user.aspx?username={u}", None),
    ("gaming", "osu!", "https://osu.ppy.sh/users/{u}", None),
    ("gaming", "Chess.com", "https://www.chess.com/member/{u}", None),
    ("gaming", "Lichess", "https://lichess.org/@/{u}", None),
    ("gaming", "Speedrun.com", "https://www.speedrun.com/user/{u}", None),
    # — Поддержка авторов / коммерция —
    ("commerce", "Patreon", "https://www.patreon.com/{u}", None),
    ("commerce", "Buy Me a Coffee", "https://www.buymeacoffee.com/{u}", None),
    ("commerce", "Gumroad", "https://{u}.gumroad.com", None),
    ("commerce", "Product Hunt", "https://www.producthunt.com/@{u}", None),
    ("commerce", "Etsy", "https://www.etsy.com/shop/{u}", None),
    # — Прочее —
    ("other", "Wattpad", "https://www.wattpad.com/user/{u}", None),
    ("other", "Goodreads", "https://www.goodreads.com/{u}", None),
    ("other", "Letterboxd", "https://letterboxd.com/{u}/", None),
    ("other", "Spotify", "https://open.spotify.com/user/{u}", None),
]


def _claimed(name: str, marker: str | None, status: int, text: str) -> bool:
    """Решение «профиль существует» по статусу и опциональному текст-маркеру."""
    if status != 200:
        return False
    if not marker:
        return True
    if marker.startswith("+"):           # маркер ПРИСУТСТВИЯ
        return marker[1:] in text
    return marker not in text            # маркер ОТСУТСТВИЯ (soft-404)


def _check(url: str, name: str, marker: str | None):
    """Вернуть (claimed: bool, status: int) или None при ошибке/таймауте."""
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT, allow_redirects=True)
        return _claimed(name, marker, r.status_code, r.text), r.status_code
    except Exception:
        return None


def _load_wmn() -> list[tuple]:
    """Загрузить датасет WhatsMyName, если он есть. Формат: {'sites':[{name,uri_check,...}]}.

    Маркеры из WMN: e_string (есть-профиль) → используем как '+', m_string (нет-профиля) → soft-404.
    Возвращает список кортежей (категория, имя, url-шаблон, marker), как PLATFORMS.
    """
    if not os.path.exists(WMN_PATH):
        return []
    try:
        with open(WMN_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    known = {p[1] for p in PLATFORMS}  # не дублировать курируемые
    out = []
    for s in data.get("sites", []):
        name = s.get("name")
        uri = s.get("uri_check")
        if not name or not uri or name in known:
            continue
        tpl = uri.replace("{account}", "{u}")
        if "{u}" not in tpl:
            continue
        if s.get("e_string"):
            marker = "+" + s["e_string"]          # presence marker
        elif s.get("m_string"):
            marker = s["m_string"]                # absence marker
        else:
            marker = None                          # rely on HTTP status (e_code обычно 200)
        out.append(("wmn", name, tpl, marker))
        if len(out) >= WMN_CAP:
            break
    return out


@enricher("username_sweep", "username")
def enrich_username(value: str) -> EnricherResult:
    res = EnricherResult("username_sweep", "username", value)
    u = value.strip().lstrip("@")
    root = res.node("username", u)

    sites = PLATFORMS + _load_wmn()
    wmn_extra = len(sites) - len(PLATFORMS)
    found_by_cat: dict[str, int] = {}

    for cat, name, tpl, marker in sites:
        out = _check(tpl.format(u=u), name, marker)
        if not out:
            continue  # таймаут/блокировка — пропускаем тихо
        claimed, status = out
        if claimed:
            found_by_cat[cat] = found_by_cat.get(cat, 0) + 1
            n = res.node("url", tpl.format(u=u), platform=name, category=cat)
            res.edge(root, n, "profile_on")
            res.fact(f"[{cat}] {name}: профіль існує — {tpl.format(u=u)}",
                     f"{name} (HTTP {status})", "D4")

    total = sum(found_by_cat.values())
    by_cat = ", ".join(f"{c}={n}" for c, n in sorted(found_by_cat.items())) or "—"
    src = f"{len(sites)} платформ" + (f" (вкл. {wmn_extra} з WhatsMyName)" if wmn_extra else "")
    res.fact(f"Знайдено профілів: {total} із {src}. За категоріями: {by_cat}. "
             f"Достовірність низька (можливі soft-404/блоки) — підтверджуй вручну.", "username_sweep")
    if not wmn_extra:
        res.fact("Глибше (сотні сайтів): поклади scripts/data/wmn-data.json (WhatsMyName) "
                 "або використай maigret/sherlock.", "tools-catalog")
    return res
