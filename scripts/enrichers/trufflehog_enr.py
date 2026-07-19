"""
trufflehog_enr.py — РЕАЛЬНЫЙ скан git-репозитория на секреты через trufflehog
(trufflesecurity/trufflehog, AGPL-3.0). В отличие от gitleaks — САМ клонирует
репо (не нужен наш git clone) и умеет ВЕРИФИЦИРОВАТЬ находки (реальный вызов
API целевого сервиса — «этот AWS-ключ живой» против «похоже на паттерн ключа»).

По умолчанию — только верифицированные (results=verified): меньше находок,
но каждая подтверждена активной проверкой, минимум false positives.
⚠️ Docker-only — статический Go-бинарник, вшит в образ.

Безопасность вывода: сырые секреты НЕ публикуются — только редактированный фрагмент.
"""
import os
import re

from ._binhelper import find_bin, run_json_stdout, unavailable_fact
from .base import EnricherResult, enricher

TIMEOUT = int(os.getenv("TRUFFLEHOG_TIMEOUT", "180"))
RESULTS = os.getenv("TRUFFLEHOG_RESULTS", "verified")  # verified | verified,unknown
INSTALL_HINT = ("Docker-образ: скачан бінарник з GitHub Releases. Вручну: "
                "curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh | sh")

GIT_HOST_RX = re.compile(r"^https?://(github\.com|gitlab\.com|bitbucket\.org)/[^/]+/[^/]+/?$", re.I)


def _redact(secret: str) -> str:
    if not secret or len(secret) <= 8:
        return "***"
    return f"{secret[:3]}…{secret[-3:]} ({len(secret)} симв.)"


@enricher("trufflehog_scan", "url")
def enrich_trufflehog(value: str) -> EnricherResult:
    res = EnricherResult("trufflehog_scan", "url", value)
    url = value.strip()
    root = res.node("url", url)

    if not GIT_HOST_RX.match(url.rstrip(".git")):
        return res  # не git-репо — тихо пропускаем

    binpath = find_bin("trufflehog", "TRUFFLEHOG_BIN")
    if not binpath:
        unavailable_fact(res, "trufflehog", INSTALL_HINT)
        return res

    rows = run_json_stdout(
        [binpath, "git", url, "--results", RESULTS, "--json", "--no-update"],
        timeout=TIMEOUT, ndjson=True,
    )
    if not rows:
        res.fact(f"trufflehog ({RESULTS}): секретів не знайдено.", "trufflehog", "C2")
        return res

    for r in rows[:50]:
        detector = r.get("DetectorName", "?")
        verified = bool(r.get("Verified"))
        secret = _redact(r.get("Raw", ""))
        meta = ((r.get("SourceMetadata") or {}).get("Data") or {}).get("Git") or {}
        file_ = meta.get("file", "?")
        commit = (meta.get("commit") or "")[:10]
        conf = "A1" if verified else "C3"  # verified=підтверджено активним викликом до сервісу
        n = res.node("url", f"{url}#{file_}", kind="secret_finding", detector=detector)
        res.edge(root, n, "leaked_secret")
        tag = "ВЕРИФІКОВАНО (активний)" if verified else "не верифіковано"
        res.fact(f"Секрет [{detector}, {tag}] у {file_} (коміт {commit}): {secret}",
                 "trufflehog", conf)

    verified_n = sum(1 for r in rows if r.get("Verified"))
    res.fact(f"trufflehog: {len(rows)} знахідок, {verified_n} верифікованих активним запитом.",
             "trufflehog", "B1" if verified_n else "C3")
    return res
