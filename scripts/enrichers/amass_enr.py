"""
amass_enr.py — РЕАЛЬНЫЙ запуск OWASP Amass v5 (owasp-amass/amass, Apache-2.0) по домену.

⚠️ Архитектурно amass — НЕ разовая команда (в отличие от theHarvester/subfinder):
это клиент-серверная система с локальной графовой базой (Open Asset Model):
  1. `amass engine`            — фоновый сервис, слушает :4000, наполняет БД.
  2. `amass enum -d domain`    — создаёт сессию на engine, отправляет цель, ждёт
                                  завершения работы (сама НЕ печатает результаты!).
  3. `amass subs -d domain -names -ip -o file` — ЧИТАЕТ результаты из локальной
                                  БД напрямую (engine для этого шага не нужен),
                                  простой текстовый вывод — одна запись на строку.
Это подтверждено чтением исходников enum/cli.go, subs/cli.go, amass_engine/cli.go —
флаги -oA/-json на enum объявлены, но нигде не используются в v5 (мёртвый код).

⚠️ ВЫКЛЮЧЕН ПО УМОЛЧАНИЮ (в отличие от theharvester/subfinder): полный цикл
engine+enum+subs занимает минуты, а не секунды — включать в обычную
последовательную цепочку domain-энричеров означало бы повторить сегодняшний
504-инцидент. Включается явно: AMASS_ENABLE=1 (для «глубокого» разового скана,
не для обычного enrich.py domain <value>).

Однопоточно (module-level lock): amass использует одну локальную БД в -dir —
конкурентные вызовы конфликтовали бы. Разовый вызов — приемлемо для «тяжёлого»
инструмента.

⚠️ Docker-only: статический Go-бинарник (owaspamass/amass образ содержит готовый
`amass`; мы качаем бинарник аналогично subfinder/gitleaks/trufflehog).
"""
import os
import shutil
import tempfile
import threading
import time

from ._binhelper import find_bin, run
from .base import EnricherResult, enricher

ENABLED = os.getenv("AMASS_ENABLE", "").lower() in ("1", "true", "yes")
ENUM_TIMEOUT_MIN = int(os.getenv("AMASS_ENUM_TIMEOUT_MIN", "3"))  # amass enum -timeout (минуты)
ENGINE_STARTUP_WAIT = float(os.getenv("AMASS_ENGINE_WAIT", "3"))  # сек, дать engine подняться
PROC_TIMEOUT = int(os.getenv("AMASS_TIMEOUT", "300"))             # общий предохранитель subprocess, сек
INSTALL_HINT = ("Docker-образ: статичний бінарник з GitHub Releases (див. Dockerfile). "
                "Вручну: CGO_ENABLED=0 go install -v github.com/owasp-amass/amass/v5/cmd/amass@main")

_LOCK = threading.Lock()  # amass працює з локальною БД у -dir — не паралелимо виклики


def _parse_subs_output(text: str) -> list[dict]:
    """Формат `amass subs -names -ip`: 'hostname [ip1, ip2]' построчно (без ip — просто hostname)."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if "[" in line:
            name, _, rest = line.partition("[")
            ips = [x.strip() for x in rest.rstrip("]").split(",") if x.strip()]
        else:
            name, ips = line, []
        name = name.strip()
        if name:
            out.append({"name": name, "ips": ips})
    return out


@enricher("amass", "domain")
def enrich_amass(value: str) -> EnricherResult:
    res = EnricherResult("amass", "domain", value)
    domain = value.strip().lower()
    root = res.node("domain", domain)

    if not ENABLED:
        res.fact("Amass вимкнено за замовчуванням (важкий клієнт-серверний скан, хвилини "
                 "не секунди) — увімкни AMASS_ENABLE=1 для розового глибокого скану.",
                 "config")
        return res

    binpath = find_bin("amass", "AMASS_BIN")
    if not binpath:
        res.fact(f"Amass недоступний у цьому деплої (потрібен Docker-образ). Встановлення: {INSTALL_HINT}",
                 "config")
        return res

    if not _LOCK.acquire(blocking=False):
        res.fact("Amass вже виконує інший скан (однопотоково через локальну БД) — спробуй пізніше.",
                 "amass")
        return res

    engine_proc = None
    workdir = tempfile.mkdtemp(prefix="amass_")
    try:
        import subprocess
        engine_proc = subprocess.Popen(
            [binpath, "engine", "-dir", workdir, "-silent"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(ENGINE_STARTUP_WAIT)
        if engine_proc.poll() is not None:
            res.error = "amass engine завершився одразу після старту (не вдалося підняти)."
            return res

        enum_proc = run(
            [binpath, "enum", "-d", domain, "-dir", workdir, "-passive",
             "-timeout", str(ENUM_TIMEOUT_MIN), "-silent"],
            timeout=PROC_TIMEOUT, cwd=workdir,
        )
        if enum_proc is None:
            res.fact("Amass enum: таймаут або помилка запуску.", "amass")
            return res

        out_file = os.path.join(workdir, "subs_out.txt")
        subs_proc = run(
            [binpath, "subs", "-d", domain, "-dir", workdir, "-names", "-ip", "-o", out_file],
            timeout=60, cwd=workdir,
        )
        if subs_proc is None or not os.path.exists(out_file):
            res.fact("Amass subs: не вдалося прочитати результати з локальної БД.", "amass")
            return res

        with open(out_file, encoding="utf-8", errors="replace") as f:
            hits = _parse_subs_output(f.read())

        for h in hits:
            name = h["name"]
            if not name or name == domain:
                continue
            dn = res.node("domain", name, role="subdomain")
            res.edge(dn, root, "subdomain_of")
            for ip in h["ips"]:
                ipn = res.node("ip", ip)
                res.edge(dn, ipn, "resolves_to")
            res.fact(f"Піддомен: {name}" + (f" [{', '.join(h['ips'])}]" if h["ips"] else ""),
                     "amass (passive)", "C3")

        res.fact(f"Amass: {len(hits)} записів (passive, timeout={ENUM_TIMEOUT_MIN}хв).", "amass", "C3")
    finally:
        if engine_proc is not None and engine_proc.poll() is None:
            engine_proc.terminate()
            try:
                engine_proc.wait(timeout=5)
            except Exception:
                engine_proc.kill()
        shutil.rmtree(workdir, ignore_errors=True)
        _LOCK.release()
    return res
