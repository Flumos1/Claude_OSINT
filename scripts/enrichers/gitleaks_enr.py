"""
gitleaks_enr.py — РЕАЛЬНЫЙ скан git-репозитория (по URL) на секреты в истории
коммитов через gitleaks (gitleaks/gitleaks, MIT).

Срабатывает только когда url похож на git-репозиторий (github.com/владелец/репо
и т.п.). Клонирует репо во временный каталог, сканирует ВСЮ историю (`gitleaks
git`), удаляет клон. ⚠️ Docker-only — статический Go-бинарник, вшит в образ.

Безопасность вывода: сырые секреты НЕ публикуются — только редактированный
фрагмент (первые/последние символы), достаточный для идентификации находки
без раскрытия рабочего значения.
"""
import os
import re
import shutil
import tempfile

from ._binhelper import find_bin, run_json_file, temp_path, unavailable_fact
from .base import EnricherResult, enricher

TIMEOUT = int(os.getenv("GITLEAKS_TIMEOUT", "180"))
CLONE_TIMEOUT = int(os.getenv("GITLEAKS_CLONE_TIMEOUT", "90"))
INSTALL_HINT = "Docker-образ: скачан бінарник з GitHub Releases. Вручну: go install github.com/gitleaks/gitleaks/v8@latest"

GIT_HOST_RX = re.compile(r"^https?://(github\.com|gitlab\.com|bitbucket\.org)/[^/]+/[^/]+/?$", re.I)


def _redact(secret: str) -> str:
    if not secret or len(secret) <= 8:
        return "***"
    return f"{secret[:3]}…{secret[-3:]} ({len(secret)} симв.)"


@enricher("gitleaks_scan", "url")
def enrich_gitleaks(value: str) -> EnricherResult:
    res = EnricherResult("gitleaks_scan", "url", value)
    url = value.strip()
    root = res.node("url", url)

    if not GIT_HOST_RX.match(url.rstrip(".git")):
        return res  # не git-репо — тихо пропускаем (не наш профиль)

    gitbin = find_bin("git")
    binpath = find_bin("gitleaks", "GITLEAKS_BIN")
    if not gitbin or not binpath:
        unavailable_fact(res, "gitleaks", INSTALL_HINT)
        return res

    tmpdir = tempfile.mkdtemp(prefix="gitleaks_")
    try:
        import subprocess
        clone = subprocess.run([gitbin, "clone", "--quiet", url, tmpdir],
                               capture_output=True, text=True, timeout=CLONE_TIMEOUT)
        if clone.returncode != 0:
            res.fact(f"Не вдалося клонувати репозиторій ({clone.returncode}) — приватний/недоступний?",
                     "gitleaks")
            return res

        out_path = temp_path(".json")
        findings = run_json_file(
            [binpath, "git", "--report-format", "json", "--report-path", out_path,
             "--exit-code", "0", tmpdir],
            out_path=out_path, timeout=TIMEOUT,
        )
        if not findings:
            res.fact("gitleaks: секретів в історії репозиторію не знайдено.", "gitleaks", "C2")
            return res

        for f in findings[:50]:  # предохранитель от гигантского вывода
            rule = f.get("RuleID", "?")
            file_ = f.get("File", "?")
            secret = _redact(f.get("Secret", ""))
            commit = (f.get("Commit") or "")[:10]
            n = res.node("url", f"{url}#{file_}", kind="secret_finding", rule=rule)
            res.edge(root, n, "leaked_secret")
            res.fact(f"Секрет [{rule}] у {file_} (коміт {commit}): {secret}",
                     "gitleaks", "B1")
        res.fact(f"gitleaks: знайдено {len(findings)} потенційних секретів в історії репозиторію.",
                 "gitleaks", "B1")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return res
