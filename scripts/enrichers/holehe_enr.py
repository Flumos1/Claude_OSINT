"""
holehe_enr.py — РЕАЛЬНЫЙ автоматический сбор: email → на каких сервисах он зарегистрирован.

Не ссылка на инструмент и не «поставь и запусти сам» — программа САМА, in-process (без
subprocess/pipx/CLI), опрашивает ~120 сервисов через их публичные signup/password-reset
эндпоинты (та же техника, что реализует библиотека Holehe: github.com/megadose/holehe,
MIT). Результат идёт напрямую в граф с provenance — как любой другой энричер.

Serverless-совместимо (важно для Vercel): все ~120 проверок идут КОНКУРЕНТНО через
httpx.AsyncClient + asyncio.gather, с общим тайм-бюджетом на весь прогон. Сайты, не
успевшие ответить в бюджет, помечаются как rateLimit (частичный, а не ошибочный
результат) — так же ведёт себя и оригинальный Holehe при таймауте/исключении модуля.

⚖️ Только по email — фактические сигналы «зарегистрирован/не зарегистрирован» из
публичных API форм восстановления пароля. Не пробив, не обход авторизации.
"""
import asyncio
import os

from .base import EnricherResult, enricher

# Бюджет намеренно с запасом от жёсткого лимита Vercel Hobby (10с на весь запрос):
# холодный старт + импорт holehe/httpx/trio + сериализация ответа тоже едят время.
BUDGET = float(os.getenv("HOLEHE_TIMEOUT", "6.5"))              # весь прогон, сек
PER_CHECK_TIMEOUT = float(os.getenv("HOLEHE_PER_CHECK_TIMEOUT", "4.5"))  # один сайт, сек

_MODULES_CACHE: list | None = None


def _load_modules() -> list:
    """Ленивая загрузка + процесс-кэш всех проверочных функций Holehe (~120 модулей)."""
    global _MODULES_CACHE
    if _MODULES_CACHE is not None:
        return _MODULES_CACHE
    from holehe.core import get_functions, import_submodules
    mods = import_submodules("holehe.modules")
    _MODULES_CACHE = get_functions(mods)
    return _MODULES_CACHE


async def _run_one(fn, email: str, client, out: list) -> None:
    try:
        await asyncio.wait_for(fn(email, client, out), timeout=PER_CHECK_TIMEOUT)
    except Exception:
        pass  # таймаут/збій сайту — просто немає результату від цього модуля


async def _collect(email: str) -> list[dict]:
    import httpx
    functions = _load_modules()
    out: list[dict] = []
    async with httpx.AsyncClient(timeout=PER_CHECK_TIMEOUT, follow_redirects=True) as client:
        tasks = [_run_one(fn, email, client, out) for fn in functions]
        try:
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=BUDGET)
        except asyncio.TimeoutError:
            pass  # частина модулів не встигла — беремо те, що вже накопичилось у out
    return out


def _run_sync(email: str) -> list[dict]:
    """Синхронна обгортка (enrich.py викликає всі енричери синхронно)."""
    try:
        return asyncio.run(_collect(email))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_collect(email))
        finally:
            loop.close()


@enricher("holehe_accounts", "email")
def enrich_holehe(value: str) -> EnricherResult:
    res = EnricherResult("holehe_accounts", "email", value)
    root = res.node("email", value.strip())
    try:
        results = _run_sync(value.strip())
    except ImportError:
        res.fact("Пакет holehe не встановлено (pip install holehe) — пропуск.", "config")
        return res
    except Exception as e:
        res.error = str(e)
        return res

    found = checked = limited = 0
    for r in results:
        checked += 1
        if r.get("rateLimit"):
            limited += 1
            continue
        if not r.get("exists"):
            continue
        found += 1
        domain = r.get("domain") or r.get("name") or "?"
        n = res.node("url", f"https://{domain}", platform=r.get("name"), kind="account")
        res.edge(root, n, "registered_on")
        extra = []
        if r.get("emailrecovery"):
            extra.append(f"recovery={r['emailrecovery']}")
        if r.get("phoneNumber"):
            extra.append(f"phone={r['phoneNumber']}")
        for k, v in (r.get("others") or {}).items():
            extra.append(f"{k}={v}")
        suffix = f" ({', '.join(extra)})" if extra else ""
        res.fact(f"Email зареєстровано на {domain}{suffix}", "holehe", "B2")

    tail = f", обмеження швидкості у {limited}" if limited else ""
    res.fact(f"Holehe: перевірено {checked} сервісів (з {len(_load_modules())}), "
             f"знайдено {found}{tail}.", "holehe")
    return res
