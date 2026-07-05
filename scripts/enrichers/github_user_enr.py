"""
GitHub-энричер (нейтральный, keyless) — ник → реальная идентичность по ПУБЛИЧНЫМ данным.

Высокий сигнал для person-OSINT: профиль (имя, компания, локация, сайт, соцсети) + публичные
commit-author email'ы из открытых событий (git-история публична). Это законный открытый
источник — данные уже опубликованы самим пользователем в своих коммитах/профиле.

API GitHub keyless: ~60 req/hr на IP. Для больших прогонов задай GITHUB_TOKEN (env) — тогда
5000 req/hr. Токен только повышает лимит, данные те же (публичные).
"""
import os
import re
import sys

import requests

from .base import EnricherResult, enricher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from image_tools import ahash, reverse_image_links
except Exception:  # image_tools недоступен — аватар-пивот отключится мягко
    ahash = reverse_image_links = None


def _add_avatar(res: EnricherResult, root, url: str) -> None:
    """Общий аватар-пивот: узел image + reverse-image ссылки + опц. aHash в attrs."""
    if reverse_image_links is None:
        return
    img = res.node("url", url, kind="avatar")
    res.edge(root, img, "avatar")
    ph = ahash(url) if ahash else None
    if ph:
        img.attrs["ahash"] = ph
        res.fact(f"Аватар aHash={ph} (для звірки облич між платформами)", "image_tools", "C3")
    links = reverse_image_links(url)
    res.fact("Reverse-image (звірка обличчя): " +
             " | ".join(f"{k}: {v}" for k, v in links.items()), "image_tools")

API = "https://api.github.com"
TIMEOUT = 15
NOREPLY = re.compile(r"noreply\.github\.com$", re.I)


def _headers() -> dict:
    h = {"User-Agent": "osint-github-enricher/1.0", "Accept": "application/vnd.github+json"}
    tok = os.getenv("GITHUB_TOKEN")
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


@enricher("github_user", "username")
def enrich_github(value: str) -> EnricherResult:
    res = EnricherResult("github_user", "username", value)
    u = value.strip().lstrip("@")
    root = res.node("username", u)
    try:
        r = requests.get(f"{API}/users/{u}", headers=_headers(), timeout=TIMEOUT)
        if r.status_code == 404:
            return res  # нет такого пользователя — тихо
        if r.status_code != 200:
            res.error = f"HTTP {r.status_code} (users/{u})"
            return res
        d = r.json()
        prof = res.node("url", d.get("html_url", f"https://github.com/{u}"), platform="GitHub")
        res.edge(root, prof, "profile_on")

        name = d.get("name")
        if name:
            pn = res.node("person", name, source="github_profile")
            res.edge(root, pn, "identity_claim")
            res.fact(f"GitHub-профіль: ім'я «{name}» (самозаявлене)", "GitHub API /users", "B3")
        for label, key in [("компанія", "company"), ("локація", "location"),
                           ("біо", "bio"), ("створено", "created_at")]:
            if d.get(key):
                res.fact(f"GitHub {label}: {d[key]}", "GitHub API /users", "B3")

        # публичный email в профиле
        if d.get("email"):
            en = res.node("email", d["email"])
            res.edge(root, en, "has_email")
            res.fact(f"Публічний email у профілі: {d['email']}", "GitHub API /users", "B2")
        # сайт/блог → домен
        blog = (d.get("blog") or "").strip()
        if blog:
            dom = re.sub(r"^https?://", "", blog).split("/")[0].lower()
            if "." in dom:
                dn = res.node("domain", dom, role="personal_site")
                res.edge(root, dn, "links_to")
                res.fact(f"Сайт у профілі: {blog} → домен {dom}", "GitHub API /users", "B3")
        # twitter
        if d.get("twitter_username"):
            tw = res.node("username", d["twitter_username"], platform="Twitter/X")
            res.edge(root, tw, "same_handle_claim")
            res.fact(f"Twitter/X у профілі: @{d['twitter_username']}", "GitHub API /users", "C3")

        res.fact(f"Публічних репозиторіїв: {d.get('public_repos', 0)}; "
                 f"підписників: {d.get('followers', 0)}", "GitHub API /users", "B2")

        # аватар → узел-изображение + reverse-image ссылки (кросс-платформенная сверка лица)
        if d.get("avatar_url"):
            _add_avatar(res, root, d["avatar_url"])

        # commit-author email'ы из публичных событий — ник → реальная почта
        _harvest_commit_emails(res, root, u)
    except Exception as e:
        res.error = str(e)
    return res


def _harvest_commit_emails(res: EnricherResult, root, u: str) -> None:
    """Достать email'ы автора из публичных PushEvent (git-история публична)."""
    try:
        r = requests.get(f"{API}/users/{u}/events/public", headers=_headers(),
                         params={"per_page": 100}, timeout=TIMEOUT)
        if r.status_code != 200:
            return
        emails: dict[str, str] = {}  # email -> имя автора
        for ev in r.json():
            if ev.get("type") != "PushEvent":
                continue
            for c in ev.get("payload", {}).get("commits", []):
                a = c.get("author", {})
                em, nm = a.get("email", ""), a.get("name", "")
                if em and not NOREPLY.search(em):
                    emails.setdefault(em.lower(), nm)
        for em, nm in emails.items():
            en = res.node("email", em)
            res.edge(root, en, "commit_email")
            who = f" (автор коміту: {nm})" if nm else ""
            res.fact(f"Email з публічних комітів: {em}{who} — сильний зв'язок нік↔пошта",
                     "GitHub API /events", "B2")
    except Exception:
        pass  # события недоступны — не критично
