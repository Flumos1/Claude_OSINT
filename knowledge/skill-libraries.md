# Внешние библиотеки скилов (оценка)

Сторонние наборы Claude-скилов, которые можно частично переиспользовать. Лицензии
проверяй перед заимствованием; берём выборочно, не «всё подряд» (чтобы не раздувать workspace).

## Anthropic-Cybersecurity-Skills (mukul975)

Репозиторий: https://github.com/mukul975/Anthropic-Cybersecurity-Skills
Оценка: 2026-06-10.

**Что это:** 754 скила в 26 доменах ИБ. Apache-2.0, ~15k★. Качество — профессиональное:
структура `SKILL.md` (YAML frontmatter) + `references/` (standards, workflows) + `scripts/` +
`assets/`. Маппинг на 5 фреймворков (MITRE ATT&CK v19.1, NIST CSF 2.0, ATLAS, D3FEND, AI RMF).
Agent-native: ~30 токенов на скан frontmatter, 500–2000 на загрузку.

**Вердикт:** качество высокое, но фокус — defensive security / forensics / malware / AD
(в основном вне нашего OSINT-скоупа). **Не импортируем массово.** Берём выборочно ~15 скилов
по OSINT/threat-intel как референс техник для наших `domain-infra` / `threat-intel` / `person-osint`.

**Полезные для нас скилы (OSINT / TI / recon):**
- `collecting-open-source-intelligence`
- `performing-open-source-intelligence-gathering`
- `conducting-external-reconnaissance-with-osint`
- `building-threat-actor-profile-from-osint`
- `performing-ai-driven-osint-correlation`
- `performing-osint-with-spiderfoot`
- `performing-subdomain-enumeration-with-subfinder`
- `performing-dns-enumeration-and-zone-transfer`
- `analyzing-certificate-transparency-for-phishing` / `analyzing-tls-certificate-transparency-logs`
- `analyzing-typosquatting-domains-with-dnstwist`
- `performing-ip-reputation-analysis-with-shodan`
- `analyzing-indicators-of-compromise`
- `analyzing-threat-intelligence-feeds` / `generating-threat-intelligence-reports`
- `analyzing-email-headers-for-phishing-investigation`
- `analyzing-ransomware-leak-site-intelligence`

**Идея к заимствованию (структура):** их формат SKILL.md с `references/` + `assets/` (чеклисты,
шаблоны) и маппингом на фреймворки — хороший паттерн. Можем усилить наши скилы `references/`
без раздувания основного файла.

**Как использовать:** не клонировать в `.claude/skills/` целиком. При работе над конкретным
доменом (напр., фишинг-домены) — открыть соответствующий скил как референс техник и адаптировать
в наш плейбук. При желании — добавить 2–3 как git-submodule в отдельную папку `reference-skills/`.
