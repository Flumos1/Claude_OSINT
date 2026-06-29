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

export interface JobEvent {
  event: "start" | "progress" | "done" | "error";
  total?: number;
  checked?: number;
  found?: number;
  mode?: string;
  result?: EnrichResult;
  error?: string;
}

export async function startJob(kind: string, value: string): Promise<string> {
  const r = await fetch("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind, value }),
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`);
  return (await r.json()).id;
}

// Подписка на прогресс джобы через SSE. Закрывает поток на done/error.
export function streamJob(id: string, onEvent: (e: JobEvent) => void): EventSource {
  const es = new EventSource(`/api/jobs/${id}/stream`);
  es.onmessage = (m) => {
    const e = JSON.parse(m.data) as JobEvent;
    onEvent(e);
    if (e.event === "done" || e.event === "error") es.close();
  };
  es.onerror = () => es.close();
  return es;
}
