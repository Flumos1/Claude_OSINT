"""
_binhelper.py — общая инфраструктура для энричеров-обёрток над РЕАЛЬНЫМИ бинарниками
(theHarvester, subfinder, gitleaks, trufflehog, Blackbird, GHunt).

Эти инструменты не работают на serverless (Vercel: нет shell/бинарников, read-only
FS) — доступны ТОЛЬКО в Docker-образе, куда вшиты на этапе сборки (см. Dockerfile).
Каждый энричер:
  1. Проверяет бинарник через shutil.which() (или явный путь — некоторые ставятся
     в изолированные venv/каталоги, не на системный PATH).
  2. Если бинарника нет — НЕ ошибка, а тихий/явный факт «недоступно в этом деплое,
     нужен Docker» (как key-gated энричеры при отсутствии ключа).
  3. Запускает с жёстким timeout (subprocess.run(..., timeout=N)) — не может
     подвесить процесс.
  4. Парсит вывод инструмента (JSON/JSONL/файл) в наш граф.
"""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

DEFAULT_TIMEOUT = int(os.getenv("BIN_ENRICHER_TIMEOUT", "90"))


def find_bin(name: str, env_var: str | None = None) -> str | None:
    """Найти бинарник: сначала явный путь из env_var, потом системный PATH."""
    if env_var:
        explicit = os.getenv(env_var)
        if explicit and Path(explicit).exists():
            return explicit
    return shutil.which(name)


def run(cmd: list[str], timeout: int = DEFAULT_TIMEOUT, cwd: str | None = None) -> subprocess.CompletedProcess | None:
    """Запустить команду с таймаутом. Возвращает CompletedProcess или None при ошибке/таймауте."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              cwd=cwd, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None


def run_json_stdout(cmd: list[str], timeout: int = DEFAULT_TIMEOUT, ndjson: bool = False):
    """Запустить и распарсить stdout как JSON (или NDJSON — список объектов по строкам)."""
    proc = run(cmd, timeout=timeout)
    if proc is None or not proc.stdout:
        return None
    if ndjson:
        out = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
        return out
    try:
        return json.loads(proc.stdout)
    except Exception:
        return None


def run_json_file(cmd: list[str], out_path: str, timeout: int = DEFAULT_TIMEOUT, cwd: str | None = None):
    """Запустить команду, которая пишет JSON в файл (не в stdout), затем прочитать файл."""
    proc = run(cmd, timeout=timeout, cwd=cwd)
    if proc is None:
        return None
    p = Path(out_path)
    if not p.exists():
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None
    finally:
        try:
            p.unlink()
        except Exception:
            pass


def temp_path(suffix: str = "") -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    try:
        os.unlink(path)  # инструменту нужен НЕсуществующий путь для создания файла
    except Exception:
        pass
    return path


def unavailable_fact(res, tool: str, how: str) -> None:
    res.fact(f"{tool} недоступен у цьому деплої (потрібен Docker-образ з вшитим бінарником). "
             f"Встановлення: {how}", "config")
