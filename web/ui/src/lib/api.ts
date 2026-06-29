// Клиент к FastAPI-бэкенду (движок энричеров). В dev проксируется Vite на :8000.

export interface Finding {
  label: string;
  text: string;
  source: string;
  confidence: string; // Admiralty, напр. "D3"
}

export interface GraphNode {
  id: string;
  type: string;
  value: string;
  attrs: Record<string, unknown>;
}

export interface GraphEdge {
  source: string;
  target: string;
  rel: string;
}

export interface EnrichResult {
  input: { type: string; value: string; country: string | null };
  enrichers_run: string[];
  nodes: GraphNode[];
  edges: GraphEdge[];
  findings: Finding[];
}

export async function enrich(
  type: string,
  value: string,
  country: string | null = "ua",
): Promise<EnrichResult> {
  const r = await fetch("/api/enrich", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type, value, country }),
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`);
  return r.json();
}
