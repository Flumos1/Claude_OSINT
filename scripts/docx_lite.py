#!/usr/bin/env python3
r"""
docx_lite.py — минимальный генератор .docx из Markdown на ЧИСТОМ stdlib (zipfile).

Без внешних зависимостей: .docx — это zip из нескольких XML. Достаточно для брифов/досье
(заголовки #/##/###, абзацы, списки «- », инлайн **bold**). Для сложной вёрстки — скил `docx`.

    from docx_lite import markdown_to_docx
    data = markdown_to_docx("# Заголовок\n\nАбзац с **важным**.\n- пункт\n")
    open("out.docx","wb").write(data)
"""
from __future__ import annotations

import io
import re
import zipfile

_CT = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>'''

_RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
# размеры в half-points: h1=16pt, h2=14pt, h3=12.5pt, body=11pt
_SIZE = {1: 32, 2: 28, 3: 25, 0: 22}


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _runs(text: str, base_size: int, bold_all: bool = False) -> str:
    """Разбить текст на runs, делая **...** жирными."""
    parts = re.split(r"(\*\*.+?\*\*)", text)
    out = []
    for p in parts:
        if not p:
            continue
        bold = bold_all or (p.startswith("**") and p.endswith("**"))
        t = p[2:-2] if (p.startswith("**") and p.endswith("**")) else p
        rpr = f'<w:rPr>{"<w:b/>" if bold else ""}<w:sz w:val="{base_size}"/></w:rPr>'
        out.append(f'<w:r>{rpr}<w:t xml:space="preserve">{_esc(t)}</w:t></w:r>')
    return "".join(out) or '<w:r><w:t/></w:r>'


def _para(text: str, level: int = 0, bullet: bool = False) -> str:
    size = _SIZE.get(level, _SIZE[0])
    spacing = '<w:spacing w:before="160" w:after="60"/>' if level else '<w:spacing w:after="80"/>'
    ind = '<w:ind w:left="360" w:hanging="180"/>' if bullet else ""
    body = ("• " + text) if bullet else text
    ppr = f"<w:pPr>{spacing}{ind}</w:pPr>"
    return f"<w:p>{ppr}{_runs(body, size, bold_all=level > 0)}</w:p>"


def markdown_to_docx(md_text: str, title: str | None = None) -> bytes:
    """Конвертировать простой Markdown в .docx (bytes)."""
    paras = []
    if title:
        paras.append(_para(title, level=1))
    for raw in md_text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith("### "):
            paras.append(_para(line[4:], level=3))
        elif line.startswith("## "):
            paras.append(_para(line[3:], level=2))
        elif line.startswith("# "):
            paras.append(_para(line[2:], level=1))
        elif re.match(r"^\s*[-*]\s+", line):
            paras.append(_para(re.sub(r"^\s*[-*]\s+", "", line), bullet=True))
        elif line.startswith("> "):
            paras.append(_para(line[2:]))
        elif set(line) <= {"-", "|", " ", ":"} and "-" in line:
            continue  # разделитель таблицы/hr — пропускаем
        else:
            paras.append(_para(line))
    document = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                f'<w:document xmlns:w="{_W}"><w:body>{"".join(paras)}'
                f'<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
                f'<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/></w:sectPr>'
                f'</w:body></w:document>')

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CT)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("word/document.xml", document)
    return buf.getvalue()


if __name__ == "__main__":  # быстрый self-test
    data = markdown_to_docx("# Тест\n\n## Раздел\n\nАбзац с **важным**.\n- один\n- два\n", )
    open("_docx_selftest.docx", "wb").write(data)
    print(f"OK: {len(data)} bytes → _docx_selftest.docx")
