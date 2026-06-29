import { useEffect, useState } from "react";
import { listCases, createCase, getCase, getCaseReport, type CaseSummary, type CaseDetail } from "@/lib/api";
import Graph from "@/Graph";

export default function CasesView() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [open, setOpen] = useState<CaseDetail | null>(null);
  const [newSlug, setNewSlug] = useState("");
  const [error, setError] = useState<string | null>(null);

  function reload() {
    listCases().then(setCases).catch(() => setCases([]));
  }
  useEffect(reload, []);

  async function create() {
    setError(null);
    try {
      const c = await createCase(newSlug);
      setNewSlug("");
      reload();
      openCase(c.slug);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function openCase(slug: string) {
    setError(null);
    try { setOpen(await getCase(slug)); } catch (e) { setError(String(e)); }
  }

  async function exportReport(slug: string) {
    const md = await getCaseReport(slug);
    const blob = new Blob([md], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${slug}-report.md`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  if (open) {
    return (
      <div style={{ padding: 16 }}>
        <button onClick={() => setOpen(null)} style={btn}>← к списку</button>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", margin: "12px 0" }}>
          <div>
            <div style={{ fontSize: 18, fontWeight: 600 }}>Кейс: {open.slug}</div>
            <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>{open.saves} сохранений · {open.nodes.length} сущностей · {open.findings.length} находок</div>
          </div>
          <button onClick={() => exportReport(open.slug)} style={{ ...btn, color: "var(--accent)", borderColor: "var(--accent)" }}>↓ Отчёт (.md)</button>
        </div>

        {open.nodes.length > 0 && <Graph nodes={open.nodes} edges={open.edges} />}

        <div style={{ fontSize: 12, color: "var(--text-muted)", margin: "16px 0 8px" }}>Находки</div>
        {open.findings.map((f, i) => (
          <div key={i} style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 12, padding: "10px 13px", marginBottom: 7 }}>
            <div style={{ fontSize: 13 }}>{f.text}</div>
            <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>{f.source}{f.confidence ? ` · ${f.confidence}` : ""}</div>
          </div>
        ))}
        {open.findings.length === 0 && <div style={{ color: "var(--text-muted)", fontSize: 13 }}>Пока ничего не сохранено. Из раздела «Поиск» → подсказка «Сохранить в кейс».</div>}
      </div>
    );
  }

  return (
    <div style={{ padding: 16 }}>
      <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 14 }}>Кейсы</div>
      {error && <div style={{ color: "var(--danger)", fontSize: 13, marginBottom: 10 }}>{error}</div>}
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <input value={newSlug} onChange={(e) => setNewSlug(e.target.value)} placeholder="новый кейс: slug (a-z, 0-9, дефис)"
          style={{ flex: 1, maxWidth: 320, background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "8px 12px", color: "var(--text-primary)", fontSize: 14, outline: "none" }} />
        <button onClick={create} disabled={!newSlug.trim()} style={{ ...btn, opacity: newSlug.trim() ? 1 : 0.5 }}>Создать</button>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 10 }}>
        {cases.map((c) => (
          <div key={c.slug} onClick={() => openCase(c.slug)} style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 12, padding: "12px 14px", cursor: "pointer" }}>
            <div style={{ fontSize: 14, fontWeight: 500, color: "var(--accent)" }}>{c.slug}</div>
            <div style={{ fontSize: 11, color: "var(--text-muted)", margin: "3px 0 6px" }}>{c.saves} сохранений</div>
            <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5, maxHeight: 54, overflow: "hidden" }}>{c.brief.replace(/[#>*]/g, "").slice(0, 120)}</div>
          </div>
        ))}
        {cases.length === 0 && <div style={{ color: "var(--text-muted)", fontSize: 13 }}>Кейсов пока нет — создайте первый.</div>}
      </div>
    </div>
  );
}

const btn: React.CSSProperties = {
  padding: "8px 14px", borderRadius: "var(--radius)", border: "1px solid var(--border-strong)",
  background: "var(--surface-1)", color: "var(--text-primary)", cursor: "pointer", fontSize: 13,
};
