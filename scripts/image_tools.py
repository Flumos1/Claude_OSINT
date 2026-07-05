#!/usr/bin/env python3
r"""
image_tools.py — аватар-пивот: reverse-image ссылки + опциональный перцептивный хеш (aHash).

Назначение: связать личность между платформами по фото профиля. Аватар (github/gravatar/…)
→ (1) ссылки на reverse-image поиск, (2) при наличии Pillow — 64-битный aHash для сравнения
аватаров между собой (один ли это человек — сигнал, не доказательство).

Pillow опционален: без него работают reverse-image ссылки; с ним — ещё и хеш/сравнение.
    pip install pillow      # включает aHash-сравнение

CLI:
    python image_tools.py links  https://example.com/avatar.jpg
    python image_tools.py hash   https://example.com/avatar.jpg
    python image_tools.py compare URL1 URL2        # хэмминг-расстояние (нужен Pillow)
"""
from urllib.parse import quote

import requests

TIMEOUT = 15
UA = {"User-Agent": "Mozilla/5.0 (compatible; osint-image/1.0)"}


def reverse_image_links(url: str) -> dict[str, str]:
    """Ссылки на reverse-image поиск по URL картинки (ручная кросс-платформенная сверка)."""
    u = quote(url, safe="")
    return {
        "Yandex": f"https://yandex.com/images/search?rpt=imageview&url={u}",
        "Google Lens": f"https://lens.google.com/uploadbyurl?url={u}",
        "Bing": f"https://www.bing.com/images/search?view=detailv2&iss=sbi&q=imgurl:{u}",
        "TinEye": f"https://tineye.com/search?url={u}",
    }


def _load_pil():
    try:
        from PIL import Image  # noqa
        return Image
    except Exception:
        return None


def ahash(url: str, hexout: bool = True):
    """64-битный average-hash аватара. None, если Pillow нет или загрузка не удалась."""
    Image = _load_pil()
    if Image is None:
        return None
    try:
        from io import BytesIO
        r = requests.get(url, headers=UA, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        img = Image.open(BytesIO(r.content)).convert("L").resize((8, 8))
        px = list(img.getdata())
        avg = sum(px) / len(px)
        bits = 0
        for p in px:
            bits = (bits << 1) | (1 if p >= avg else 0)
        return f"{bits:016x}" if hexout else bits
    except Exception:
        return None


def hamming(h1: str, h2: str) -> int | None:
    """Расстояние Хэмминга между двумя hex-хешами (кол-во разных бит). Меньше = похожее."""
    if not h1 or not h2:
        return None
    try:
        return bin(int(h1, 16) ^ int(h2, 16)).count("1")
    except Exception:
        return None


def similarity_verdict(dist: int | None) -> str:
    if dist is None:
        return "нет хеша (Pillow не установлен или загрузка не удалась)"
    if dist <= 6:
        return f"очень похожи (dist={dist}) — вероятно одно фото/человек (сигнал, не доказательство)"
    if dist <= 12:
        return f"похожи (dist={dist}) — возможно связаны, проверь вручную"
    return f"различаются (dist={dist}) — вероятно разные изображения"


def main():
    import sys
    if len(sys.argv) < 3:
        sys.exit("usage: image_tools.py {links|hash|compare} URL [URL2]")
    cmd, url = sys.argv[1], sys.argv[2]
    if cmd == "links":
        for name, link in reverse_image_links(url).items():
            print(f"{name}: {link}")
    elif cmd == "hash":
        h = ahash(url)
        print(h or "нет хеша (установи pillow: pip install pillow)")
    elif cmd == "compare" and len(sys.argv) >= 4:
        h1, h2 = ahash(url), ahash(sys.argv[3])
        d = hamming(h1, h2)
        print(f"aHash1={h1}  aHash2={h2}")
        print("Вердикт:", similarity_verdict(d))
    else:
        sys.exit("usage: image_tools.py {links|hash|compare} URL [URL2]")


if __name__ == "__main__":
    main()
