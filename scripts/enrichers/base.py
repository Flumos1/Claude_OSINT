"""
base.py — контракт энричеров (по мотивам flowsint flowsint-enrichers).

Идея: каждый энричер принимает одну сущность (entity) определённого типа и
возвращает граф — узлы (Node), связи (Edge) и факты (Finding) с provenance.
Узлы/связи совместимы с граф-моделью (Neo4j-friendly), чтобы позже без переписывания
импортировать во flowsint, если будем поднимать платформу (стратегия А).

Энричер регистрируется декоратором @enricher(name, input_type). Раннер enrich.py
диспетчеризует по input_type.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

# Централизованная загрузка scripts/.env — чтобы любой key-gated энричер видел ключи.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except Exception:
    pass

ENTITY_TYPES = {
    "domain", "ip", "email", "username", "phone",
    "company", "person", "crypto", "url",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Node:
    type: str
    value: str
    attrs: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        return f"{self.type}:{self.value.strip().lower()}"


@dataclass
class Edge:
    source: str  # Node.id
    target: str  # Node.id
    rel: str     # тип связи: resolves_to, subdomain_of, uses_ns, breached_in, ...


@dataclass
class Finding:
    """Факт/наблюдение с источником. label: FACT|INFERENCE|HYPOTHESIS."""
    label: str
    text: str
    source: str
    confidence: str = ""  # Admiralty [A1..F6], опционально


@dataclass
class EnricherResult:
    enricher: str
    input_type: str
    input_value: str
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    error: str = ""
    collected_at: str = field(default_factory=_now)

    def node(self, type_: str, value: str, **attrs) -> Node:
        n = Node(type_, value, dict(attrs))
        self.nodes.append(n)
        return n

    def edge(self, source: Node | str, target: Node | str, rel: str) -> None:
        s = source.id if isinstance(source, Node) else source
        t = target.id if isinstance(target, Node) else target
        self.edges.append(Edge(s, t, rel))

    def fact(self, text: str, source: str, confidence: str = "") -> None:
        self.findings.append(Finding("FACT", text, source, confidence))

    def to_dict(self) -> dict:
        return asdict(self)


# input_type -> list[(name, fn, country)]; country=None означает страново-нейтральный
REGISTRY: dict[str, list[tuple[str, callable, str | None]]] = {}


def enricher(name: str, input_type: str, country: str | None = None):
    """
    Декоратор регистрации энричера. fn(value:str) -> EnricherResult.
    country: ISO-2 код ('ua','ru','cz'...) для страново-специфичных энричеров (реестры),
             или None для нейтральных (domain/ip/email — работают для любой страны).
    """
    if input_type not in ENTITY_TYPES:
        raise ValueError(f"Неизвестный тип сущности: {input_type}")

    def deco(fn):
        REGISTRY.setdefault(input_type, []).append((name, fn, country))
        return fn

    return deco


def enrichers_for(input_type: str, country: str | None = None) -> list[tuple[str, callable]]:
    """Энричеры для типа: страново-нейтральные всегда + совпадающие по стране."""
    out = []
    for name, fn, c in REGISTRY.get(input_type, []):
        if c is None or country is None or c == country:
            out.append((name, fn))
    return out
