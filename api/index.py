"""
Vercel serverless entrypoint (ASGI) — обслуживает ТОЛЬКО /api/* (React-статику раздаёт
Vercel CDN из web/static/dist, см. vercel.json).

Добавляем пути репозитория в sys.path и импортируем FastAPI-приложение из web/app.py.
На Vercel: VERCEL=1 (secure-cookie), персистентность auth/кейсов — через Upstash KV
(KV_REST_API_URL/TOKEN), фоновые сканы — инлайновый SSE (/api/scan/stream).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "web"))
sys.path.insert(0, str(ROOT / "scripts"))

from app import app  # noqa: E402,F401  (ASGI-приложение для Vercel)
