"""
sanctions.py — живая проверка по санкциям/PEP через OpenSanctions API (key-gated).

OpenSanctions агрегирует OFAC/EU/UK/UN/нац. списки + PEP. Хостинговый API требует ключ
(OPENSANCTIONS_API_KEY). Без ключа — None (используем deep-ссылку). Используется person_search.
"""
import os

import requests

API = "https://api.opensanctions.org/search/default"
TIMEOUT = 20


def check_opensanctions(name: str, key: str | None = None) -> list[dict] | None:
    """Возвращает список совпадений [{caption, schema, topics, datasets, score}] или None (нет ключа/ошибка)."""
    key = key or os.getenv("OPENSANCTIONS_API_KEY")
    if not key:
        return None
    try:
        r = requests.get(API, params={"q": name, "limit": 8},
                         headers={"Authorization": f"ApiKey {key}", "User-Agent": "osint-sanctions/1.0"},
                         timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        out = []
        for res in r.json().get("results", []):
            props = res.get("properties", {})
            out.append({
                "caption": res.get("caption"),
                "schema": res.get("schema"),
                "topics": props.get("topics", []),
                "datasets": res.get("datasets", [])[:4],
                "score": round(res.get("score", 0), 2),
            })
        return out
    except Exception:
        return None
