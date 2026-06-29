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

export interface CaseSummary { slug: string; brief: string; saves: number }
export interface CaseDetail extends EnrichResult { slug: string; saves: number }

export async function listCases(): Promise<CaseSummary[]> {
  const r = await fetch("/api/cases");
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function createCase(slug: string, title = "", basis = ""): Promise<{ slug: string }> {
  const r = await fetch("/api/cases", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slug, title, basis }),
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`);
  return r.json();
}

export async function saveToCase(slug: string, result: EnrichResult): Promise<{ saves: number }> {
  const r = await fetch(`/api/cases/${slug}/save`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ result }),
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`);
  return r.json();
}

export async function getCase(slug: string): Promise<CaseDetail> {
  const r = await fetch(`/api/cases/${slug}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function getCaseReport(slug: string): Promise<string> {
  const r = await fetch(`/api/cases/${slug}/report`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()).markdown;
}

export interface ToolItem {
  name: string;
  url: string;
  desc: string;
  category: string;
  flag: string | null;
}

export interface ToolsResponse {
  total: number;
  all_total: number;
  flagged_total: number;
  categories: { name: string; count: number }[];
  items: ToolItem[];
}

export interface PersonReq {
  name: string; dob?: string; rnokpp?: string; email?: string;
  phone?: string; username?: string; countries: string[];
}

export interface PersonResult {
  basis: string;
  name_variants: string[];
  id_check: Record<string, unknown>;
  registries: Record<string, { name: string; url: string; note: string }[]>;
  sanctions: unknown;
  notes: string[];
  nodes: GraphNode[];
  edges: GraphEdge[];
  findings: Finding[];
}

export async function searchPerson(req: PersonReq): Promise<PersonResult> {
  const r = await fetch("/api/person", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req),
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`);
  return r.json();
}

export async function personReport(req: PersonReq): Promise<string> {
  const r = await fetch("/api/person/report", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()).markdown;
}

export interface CuratedTool {
  id: string; name: string; category: string; url: string;
  method: string; install: string; note?: string;
}

export async function fetchCurated(): Promise<{ tools: CuratedTool[]; meta: Record<string, string> }> {
  const r = await fetch("/api/tools/curated");
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function fetchTools(p: { q?: string; category?: string; flagged?: boolean; limit?: number }): Promise<ToolsResponse> {
  const u = new URLSearchParams();
  if (p.q) u.set("q", p.q);
  if (p.category) u.set("category", p.category);
  if (p.flagged) u.set("flagged", "true");
  u.set("limit", String(p.limit ?? 60));
  const r = await fetch(`/api/tools?${u.toString()}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
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
