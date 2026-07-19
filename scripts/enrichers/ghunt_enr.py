"""
ghunt_enr.py — РЕАЛЬНЫЙ запуск GHunt (mxrch/GHunt, AGPL-3.0) по email: публичные
данные Google-аккаунта (имя, фото профиля, Gaia ID, публичные Maps/Calendar
метаданные, если они открыты) через официальные Google API от лица АВТОРИЗОВАННОГО
аккаунта оператора.

⚠️ ЭТО НЕ «вбив email — отримав дані» без налаштувань. GHunt працює ЛИШЕ від імені
залогіненого Google-акаунту ОПЕРАТОРА (`ghunt login`) — разова, РУЧНА настройка:
    docker compose exec osint ghunt login
Оператор сам вставляє СВОЇ куки (через розширення GHunt Companion або вручну).
Ми НІКОЛИ не автоматизуємо і не запитуємо чужі облікові дані/куки — це поза
межами того, що робить агент. Без виконаного `ghunt login` енричер лише повідомляє
про потребу в цьому кроці і не падає.

⚠️ Docker-only: pipx install ghunt (ізольований venv від pipx). На Vercel — недоступно.
"""
import json
import os
from pathlib import Path

from ._binhelper import find_bin, run, temp_path
from .base import EnricherResult, enricher

TIMEOUT = int(os.getenv("GHUNT_TIMEOUT", "60"))
CREDS_PATH = Path(os.getenv("GHUNT_CREDS_PATH", str(Path.home() / ".malfrats" / "ghunt" / "creds.m")))
INSTALL_HINT = "Docker-образ: pipx install ghunt (див. Dockerfile)."
LOGIN_HINT = ("GHunt встановлено, але НЕ авторизовано. Розова ручна настройка (виконує ОПЕРАТОР, "
             "не автоматизується): `docker compose exec osint ghunt login` → вставити СВОЇ Google-куки "
             "(розширення GHunt Companion або вручну). Після цього email-пошук стане автоматичним.")


def _pluck(d: dict, *path, default=None):
    cur = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


@enricher("ghunt_email", "email")
def enrich_ghunt(value: str) -> EnricherResult:
    res = EnricherResult("ghunt_email", "email", value)
    email = value.strip()
    root = res.node("email", email)

    binpath = find_bin("ghunt", "GHUNT_BIN")
    if not binpath:
        res.fact(f"GHunt недоступний у цьому деплої (потрібен Docker-образ). Встановлення: {INSTALL_HINT}",
                 "config")
        return res
    if not CREDS_PATH.exists():
        res.fact(LOGIN_HINT, "config")
        return res

    out_path = temp_path(".json")
    proc = run([binpath, "email", email, "--json", out_path], timeout=TIMEOUT)
    if proc is None:
        res.fact("GHunt: таймаут або помилка запуску.", "ghunt")
        return res
    if not os.path.exists(out_path):
        res.fact("GHunt: ціль не знайдена або не є публічним Google-акаунтом.", "ghunt", "D3")
        return res

    try:
        with open(out_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        res.fact("GHunt: не вдалося прочитати результат (некоректний JSON).", "ghunt")
        return res
    finally:
        try:
            os.remove(out_path)
        except Exception:
            pass

    # Захисне вилучення ключових сигналів — повна вкладена структура GHunt (Maps,
    # Calendar, Photos) варіативна; беремо найцінніше, решту лишаємо в exports.
    name = _pluck(data, "PROFILE", "name") or _pluck(data, "name")
    photo = _pluck(data, "PROFILE", "profile_photo_url") or _pluck(data, "profile_photo_url")
    gaia = data.get("gaia_id") or data.get("gaiaId")

    if name:
        pn = res.node("person", name, source="ghunt_google_account")
        res.edge(root, pn, "identity_claim")
        res.fact(f"Google-акаунт: ім'я «{name}»", "GHunt", "B3")
    if photo:
        res.fact(f"Фото профілю Google: {photo}", "GHunt", "B3")
    if gaia:
        res.fact(f"Gaia ID: {gaia}", "GHunt", "B2")
    if not (name or photo or gaia):
        res.fact("GHunt: акаунт знайдено, але без публічно доступних деталей у витягнутих полях "
                 "(перевір повний JSON вручну — структура варіативна).", "ghunt", "C3")
    else:
        res.fact("GHunt: знайдено публічний Google-акаунт, пов'язаний з email.", "ghunt", "B2")
    return res
