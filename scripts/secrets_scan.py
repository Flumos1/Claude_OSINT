#!/usr/bin/env python3
"""
secrets_scan.py — поиск утёкших секретов (API-ключи, токены, приватные ключи) в тексте/на странице.

Каталог regex-паттернов в стиле gitleaks/trufflehog. Применение: проверка СВОИХ ассетов
(страницы, JS-бандлы, репозитории) на случайно открытые секреты — для защиты (threat-intel).
Не используй для эксплуатации чужих секретов.

CLI:
    python secrets_scan.py https://example.com/app.js
    python secrets_scan.py path/to/file.txt
"""
import re
import sys

PATTERNS = {
    "AWS Access Key": r"AKIA[0-9A-Z]{16}",
    "AWS Secret Key": r"(?i)aws_secret[^\n]{0,20}[:=]\s*['\"]?([A-Za-z0-9/+=]{40})",
    "Google API Key": r"AIza[0-9A-Za-z\-_]{35}",
    "Google OAuth": r"[0-9]+-[0-9A-Za-z_]{32}\.apps\.googleusercontent\.com",
    "GitHub PAT": r"gh[pousr]_[0-9A-Za-z]{36,}",
    "GitHub Fine-grained": r"github_pat_[0-9A-Za-z_]{82}",
    "Slack Token": r"xox[baprs]-[0-9A-Za-z-]{10,}",
    "Slack Webhook": r"https://hooks\.slack\.com/services/[A-Za-z0-9/]{40,}",
    "Stripe Key": r"(?:sk|pk|rk)_(?:live|test)_[0-9A-Za-z]{24,}",
    "Twilio SID": r"AC[0-9a-fA-F]{32}",
    "SendGrid Key": r"SG\.[0-9A-Za-z_\-]{22}\.[0-9A-Za-z_\-]{43}",
    "Mailgun Key": r"key-[0-9a-zA-Z]{32}",
    "Telegram Bot Token": r"[0-9]{8,10}:[A-Za-z0-9_-]{35}",
    "Discord Token": r"[MN][A-Za-z\d]{23}\.[\w-]{6}\.[\w-]{27}",
    "Discord Webhook": r"https://discord(?:app)?\.com/api/webhooks/[0-9]+/[A-Za-z0-9_-]+",
    "npm Token": r"npm_[0-9A-Za-z]{36}",
    "Heroku Key": r"(?i)heroku[^\n]{0,15}[:=]\s*['\"]?([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    "Private Key Block": r"-----BEGIN (?:RSA|EC|DSA|OPENSSH|PGP)? ?PRIVATE KEY-----",
    "JWT": r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
    "Generic API key": r"(?i)(?:api[_-]?key|apikey|access[_-]?token|secret)[\"'\s:=]{1,4}([0-9a-zA-Z\-_]{16,45})",
    "Basic Auth in URL": r"https?://[^/\s:@]+:[^/\s:@]+@[^/\s]+",
    "Firebase URL": r"https://[a-z0-9-]+\.firebaseio\.com",
    "OpenAI Key": r"sk-[A-Za-z0-9]{20}T3BlbkFJ[A-Za-z0-9]{20}",
    "Anthropic Key": r"sk-ant-[A-Za-z0-9_-]{20,}",
}


def mask(s: str) -> str:
    s = s if len(s) <= 80 else s[:80] + "…"
    return s[:6] + "…" + s[-4:] if len(s) > 14 else s


def scan(text: str) -> list[dict]:
    hits, seen = [], set()
    for name, pat in PATTERNS.items():
        for m in re.finditer(pat, text):
            val = m.group(0)
            key = (name, val)
            if key in seen:
                continue
            seen.add(key)
            hits.append({"type": name, "match": mask(val)})
    return hits


def _get_text(src: str) -> str:
    if src.startswith("http://") or src.startswith("https://"):
        import requests
        return requests.get(src, headers={"User-Agent": "osint-secrets/1.0"}, timeout=20).text
    with open(src, encoding="utf-8", errors="ignore") as f:
        return f.read()


def main():
    if len(sys.argv) < 2:
        sys.exit("Использование: python secrets_scan.py <url|файл>")
    src = sys.argv[1]
    hits = scan(_get_text(src))
    print(f"\nСканирование {src}: найдено {len(hits)} потенциальных секретов "
          f"(паттернов в каталоге: {len(PATTERNS)})\n")
    for h in hits:
        print(f"  [{h['type']}] {h['match']}")
    if not hits:
        print("  — секретов не обнаружено.")


if __name__ == "__main__":
    main()
