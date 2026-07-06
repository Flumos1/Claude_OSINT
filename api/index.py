"""
Vercel serverless entrypoint (ASGI).

Vercel-рантайм @vercel/python поднимает ASGI-приложение `app`. Здесь мы добавляем
пути репозитория в sys.path и импортируем FastAPI-приложение из web/app.py.
На Vercel окружение read-only (VERCEL=1) — «Сохранить в кейс» отключается автоматически.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "web"))
sys.path.insert(0, str(ROOT / "scripts"))

from app import app  # noqa: E402,F401  (ASGI-приложение для Vercel)
