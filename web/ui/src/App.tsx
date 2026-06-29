import { useMemo, useState, type FormEvent } from "react";
import { detect, type Guess } from "@/lib/detect";
import { enrich, startJob, streamJob, type EnrichResult, type Finding } from "@/lib/api";
import { suggest, type Suggestion } from "@/lib/suggest";
import ToolsView from "@/ToolsView";
import CasesView from "@/CasesView";
import PersonView from "@/PersonView";
import Graph from "@/Graph";
import { listCases, createCase, saveToCase } from "@/lib/api";

const NAV = [
  { id: "search", label: "Поиск" },
  { id: "graph", label: "Граф" },
  { id: "person", label: "Поиск ФЛ" },
  { id: "tools", label: "Инструменты" },
  { id: "cases", label: "Кейсы" },
];

function gradeTone(c: string): "success" | "warning" | "danger" | "muted" {
  if (!c) return "muted";
  if (["A", "B"].includes(c[0]) || c === "C3" || c === "D3") return "success";
  if (c === "D4" || c === "C4" || c[0] === "C") return "warning";
  if (c === "D5" || ["E", "F"].includes(c[0])) return "danger";
  return "muted";
}

const TONE: Record<string, { fg: string; bg: string }> = {
  success: { fg: "var(--success)", bg: "var(--success-bg)" },
  warning: { fg: "var(--warning)", bg: "var(--warning-bg)" },
  danger: { fg: "var(--danger)", bg: "var(--danger-bg)" },
  muted: { fg: "var(--text-muted)", bg: "var(--surface-2)" },
};

function scoreOf(text: string): string | null {
  const m = text.match(/\((\d{1,3})%/);
  return m ? `${m[1]}%` : null;
}

export default function App() {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<EnrichResult | null>(null);
  const [progress, setProgress] = useState<{ checked: number; total: number; found: number; mode?: string } | null>(null);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [view, setView] = useState("search");

  const guesses = useMemo<Guess[]>(() => detect(query), [query]);
  const suggestions: Suggestion[] = useMemo(() => (result ? suggest(result) : []), [result]);

  function toggleTheme() {
    const t = theme === "dark" ? "light" : "dark";
    setTheme(t);
    document.documentElement.setAttribute("data-theme", t);
  }

  async function run(type: string, value: string, country?: string) {
    setLoading(true);
    setError(null);
    try {
      const r = await enrich(type, value, country ?? "ua");
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  async function runDeep(value: string) {
    setLoading(true);
    setError(null);
    setProgress({ checked: 0, total: 0, found: 0 });
    try {
      const id = await startJob("username_deep", value);
      streamJob(id, (e) => {
        if (e.event === "start") setProgress({ checked: 0, total: e.total ?? 0, found: 0, mode: e.mode });
        else if (e.event === "progress") setProgress({ checked: e.checked ?? 0, total: e.total ?? 0, found: e.found ?? 0, mode: e.mode });
        else if (e.event === "done" && e.result) { setResult(e.result); setProgress(null); setLoading(false); }
        else if (e.event === "error") { setError(e.error ?? "ошибка джобы"); setProgress(null); setLoading(false); }
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setProgress(null);
      setLoading(false);
    }
  }

  async function saveCurrent() {
    if (!result) return;
    const existing = await listCases().catch(() => []);
    const list = existing.map((c) => c.slug).join(", ");
    const slug = window.prompt(
      `В какой кейс сохранить?${list ? "\nСуществующие: " + list : ""}\nВведите slug (новый будет создан):`,
      existing[0]?.slug || "",
    );
    if (!slug) return;
    try {
      if (!existing.some((c) => c.slug === slug)) await createCase(slug);
      const r = await saveToCase(slug, result);
      window.alert(`Сохранено в «${slug}» (всего сохранений: ${r.saves}).`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const g = guesses[active] ?? guesses[0];
    if (!g) return;
    const v = query.trim();
    setQuery(v);
    run(g.type, v, g.country);
  }

  const found = result?.findings.filter((f) => f.confidence) ?? [];

  return (
    <div style={{ display: "flex", height: "100%" }}>
      <aside style={{ width: 184, flexShrink: 0, background: "var(--surface-1)", borderRight: "1px solid var(--border)", padding: 14, display: "flex", flexDirection: "column", gap: 2 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9, padding: "4px 8px 16px" }}>
          <div style={{ width: 26, height: 26, borderRadius: 7, background: "var(--accent-bg)", color: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 600 }}>OS</div>
          <span style={{ fontSize: 14, fontWeight: 600 }}>Claude OSINT</span>
        </div>
        {NAV.map((n) => (
          <div key={n.id} onClick={() => setView(n.id)} style={{ padding: "8px 10px", borderRadius: "var(--radius)", fontSize: 13, color: n.id === view ? "var(--accent)" : "var(--text-secondary)", background: n.id === view ? "var(--accent-bg)" : "transparent", cursor: "pointer" }}>
            {n.label}
          </div>
        ))}
        <div style={{ marginTop: "auto", fontSize: 11, color: "var(--text-muted)", lineHeight: 1.5, padding: "10px 8px 0" }}>
          Только открытые источники. Этичный OSINT.
        </div>
      </aside>

      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", overflow: "auto" }}>
        <header style={{ position: "sticky", top: 0, background: "var(--surface-0)", borderBottom: "1px solid var(--border)", padding: 14, zIndex: 2, display: "flex", gap: 8, alignItems: "center" }}>
          {view === "search" ? (
            <form onSubmit={onSubmit} style={{ flex: 1, display: "flex", gap: 8, alignItems: "center" }}>
              <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 8, background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "8px 12px" }}>
                <span style={{ color: "var(--text-muted)" }}>⌕</span>
                <input
                  value={query}
                  onChange={(e) => { setQuery(e.target.value); setActive(0); }}
                  placeholder="Email, домен, IP, телефон, ник, ЄДРПОУ/ИНН, ФИО…"
                  style={{ flex: 1, background: "transparent", border: "none", outline: "none", color: "var(--text-primary)", fontSize: 14 }}
                />
                {guesses.slice(0, 3).map((g, i) => (
                  <button type="button" key={g.label + i} onClick={() => setActive(i)}
                    style={{ fontSize: 11, padding: "3px 9px", borderRadius: 20, border: "none", cursor: "pointer",
                      background: i === active ? "var(--accent-bg)" : "var(--surface-2)",
                      color: i === active ? "var(--accent)" : "var(--text-secondary)" }}>
                    {i === 0 ? "авто: " : ""}{g.label}
                  </button>
                ))}
              </div>
              <button type="submit" disabled={loading || !query.trim()}
                style={{ padding: "9px 16px", borderRadius: "var(--radius)", border: "none", cursor: "pointer", fontSize: 14, fontWeight: 500, background: "var(--accent)", color: "#fff", opacity: loading || !query.trim() ? 0.5 : 1 }}>
                {loading ? "…" : "Обогатить"}
              </button>
            </form>
          ) : (
            <div style={{ flex: 1, fontSize: 14, color: "var(--text-secondary)" }}>
              {NAV.find((n) => n.id === view)?.label}
            </div>
          )}
          <button type="button" onClick={toggleTheme} title="Тема"
            style={{ padding: "9px 11px", borderRadius: "var(--radius)", border: "1px solid var(--border)", background: "var(--surface-1)", color: "var(--text-secondary)", cursor: "pointer" }}>◐</button>
        </header>

        {view === "tools" && <ToolsView />}
        {view === "cases" && <CasesView />}
        {view === "graph" && (
          result && result.nodes.length > 0 ? (
            <div style={{ padding: 16 }}>
              <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>
                Граф · {result.input.type}: <span className="mono">{result.input.value}</span>
              </div>
              <Graph nodes={result.nodes} edges={result.edges} height={520} />
            </div>
          ) : (
            <div style={{ padding: 40, textAlign: "center", color: "var(--text-muted)", fontSize: 14 }}>
              Сначала выполните поиск в разделе «Поиск».
            </div>
          )
        )}
        {view === "person" && <PersonView />}

        <main style={{ padding: 16, flex: 1, display: view === "search" ? "block" : "none" }}>
          {error && (
            <div style={{ padding: 12, borderRadius: "var(--radius)", background: "var(--danger-bg)", color: "var(--danger)", fontSize: 13, marginBottom: 14 }}>
              Ошибка: {error}
            </div>
          )}

          {progress && (
            <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 12, padding: 14, marginBottom: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 8 }}>
                <span>Deep-скан{progress.mode ? ` · ${progress.mode}` : ""}</span>
                <span className="mono" style={{ color: "var(--text-secondary)" }}>
                  {progress.checked}/{progress.total || "…"} · найдено {progress.found}
                </span>
              </div>
              <div style={{ height: 6, background: "var(--surface-2)", borderRadius: 6, overflow: "hidden" }}>
                <div style={{ height: "100%", width: `${progress.total ? Math.round((progress.checked / progress.total) * 100) : 0}%`, background: "var(--accent)", transition: "width .2s" }} />
              </div>
            </div>
          )}

          {!result && !error && !progress && (
            <div style={{ textAlign: "center", color: "var(--text-muted)", padding: "80px 20px" }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>⊹</div>
              <p style={{ fontSize: 14 }}>Введите сущность — тип определится автоматически.</p>
            </div>
          )}

          {result && (
            <>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 10, marginBottom: 16 }}>
                <Stat label="Найдено" value={found.length} />
                <Stat label="Высокая ≥78%" value={found.filter((f) => gradeTone(f.confidence) === "success").length} color="var(--success)" />
                <Stat label="Проверить" value={found.filter((f) => gradeTone(f.confidence) !== "success").length} color="var(--warning)" />
                <Stat label="Энричеров" value={result.enrichers_run.length} />
              </div>

              <div style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>
                    Находки · {result.input.type}: <span className="mono">{result.input.value}</span>
                  </div>
                  {result.findings.map((f, i) => <FindingRow key={i} f={f} />)}
                </div>

                {suggestions.length > 0 && (
                  <div style={{ width: 230, flexShrink: 0 }}>
                    <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>💡 Подсказки · что дальше</div>
                    {suggestions.map((s, i) => (
                      <div key={i} onClick={() => {
                        if (s.action === "deep") runDeep(result.input.value);
                        else if (s.action === "save") saveCurrent();
                        else if (s.pivot) run(s.pivot.type, s.pivot.value, s.pivot.country);
                      }}
                        style={{ marginBottom: 8, padding: "11px 13px", borderRadius: 12, cursor: s.pivot || s.action ? "pointer" : "default",
                          background: s.tone === "accent" ? "var(--accent-bg)" : "var(--surface-1)",
                          border: "1px solid var(--border)" }}>
                        <div style={{ fontSize: 13, fontWeight: 500, color: s.tone === "accent" ? "var(--accent)" : "var(--text-primary)" }}>{s.title}</div>
                        <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5, marginTop: 3 }}>{s.desc}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div style={{ background: "var(--surface-1)", borderRadius: "var(--radius)", padding: "11px 13px" }}>
      <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 500, color: color ?? "var(--text-primary)" }}>{value}</div>
    </div>
  );
}

function FindingRow({ f }: { f: Finding }) {
  const tone = TONE[gradeTone(f.confidence)];
  const score = scoreOf(f.text);
  return (
    <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 12, padding: "11px 14px", marginBottom: 8, display: "flex", alignItems: "center", gap: 12 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, lineHeight: 1.5 }}>{f.text}</div>
        <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 3 }}>{f.source}</div>
      </div>
      {(score || f.confidence) && (
        <div style={{ textAlign: "right", flexShrink: 0 }}>
          {score && <div style={{ fontSize: 14, fontWeight: 500, color: tone.fg }}>{score}</div>}
          {f.confidence && <div style={{ fontSize: 11, padding: "2px 7px", borderRadius: 20, background: tone.bg, color: tone.fg }}>{f.confidence}</div>}
        </div>
      )}
    </div>
  );
}
