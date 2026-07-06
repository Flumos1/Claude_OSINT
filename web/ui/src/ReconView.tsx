import { useState, type FormEvent } from "react";
import { recon, fetchReport, type ReconResult, type LedgerRow, type ReportFmt } from "@/lib/api";
import Graph from "@/Graph";

const TIER: Record<string, { color: string; emoji: string }> = {
  CONFIRMED: { color: "var(--success)", emoji: "🟢" },
  PROBABLE: { color: "var(--warning)", emoji: "🟡" },
  POSSIBLE: { color: "var(--text-muted)", emoji: "⚪" },
};

const field: React.CSSProperties = {
  background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: "var(--radius)",
  padding: "8px 11px", color: "var(--text-primary)", fontSize: 13, width: "100%", boxSizing: "border-box",
};

export default function ReconView() {
  const [form, setForm] = useState({ basis: "", name: "", email: "", username: "", github: "", phone: "", hops: 2 });
  const [res, setRes] = useState<ReconResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const upd = (k: string, v: string | number) => setForm((f) => ({ ...f, [k]: v }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!form.basis.trim()) { setError("Укажите правовое основание — это обязательно."); return; }
    setLoading(true); setError(null); setRes(null);
    try { setRes(await recon(form)); }
    catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setLoading(false); }
  }

  async function exportReport(fmt: ReportFmt) {
    try { await fetchReport("/api/recon/report", form, fmt); }
    catch (err) { setError(err instanceof Error ? err.message : String(err)); }
  }

  const counts = { CONFIRMED: 0, PROBABLE: 0, POSSIBLE: 0 };
  (res?.ledger ?? []).forEach((l) => { counts[l.tier]++; });
  const rows = (tier: keyof typeof counts) => (res?.ledger ?? []).filter((l) => l.tier === tier);

  return (
    <div style={{ padding: 16, maxWidth: 960 }}>
      <div style={{ background: "var(--warning-bg)", color: "var(--warning)", borderRadius: "var(--radius)", padding: "9px 12px", fontSize: 12.5, marginBottom: 14 }}>
        ⚖️ Многошаговая разведка личности по открытым источникам — только при правовом основании.
        Движок коррелирует находки и размечает достоверность связи (ник/имя ≠ тот же человек).
      </div>

      <form onSubmit={submit} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 10, marginBottom: 16 }}>
        <label style={{ gridColumn: "1 / -1", fontSize: 12, color: "var(--text-secondary)" }}>
          ⚖️ Правовое основание *
          <input style={field} value={form.basis} onChange={(e) => upd("basis", e.target.value)} placeholder="KYC контрагента / DD / расследование…" />
        </label>
        {([["name", "ФИО / ПІБ"], ["email", "Email(ы), через запятую"], ["username", "Username(ы)"], ["github", "GitHub"], ["phone", "Телефон"]] as const).map(([k, ph]) => (
          <label key={k} style={{ fontSize: 12, color: "var(--text-secondary)" }}>{ph}
            <input style={field} value={(form as Record<string, string | number>)[k] as string} onChange={(e) => upd(k, e.target.value)} placeholder={ph} />
          </label>
        ))}
        <label style={{ fontSize: 12, color: "var(--text-secondary)" }}>Глубина (hops)
          <select style={field} value={form.hops} onChange={(e) => upd("hops", Number(e.target.value))}>
            <option value={1}>1</option><option value={2}>2</option><option value={3}>3</option>
          </select>
        </label>
        <button type="submit" disabled={loading} style={{ gridColumn: "1 / -1", padding: "10px", borderRadius: "var(--radius)", border: "none", background: "var(--accent)", color: "#fff", cursor: "pointer", fontSize: 14, opacity: loading ? 0.6 : 1 }}>
          {loading ? "Пивотинг и корреляция…" : "Запустить recon"}
        </button>
      </form>

      {error && <div style={{ padding: 12, borderRadius: "var(--radius)", background: "var(--danger-bg)", color: "var(--danger)", fontSize: 13, marginBottom: 14 }}>Ошибка: {error}</div>}

      {res && (
        <>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center", marginBottom: 16 }}>
            {(["CONFIRMED", "PROBABLE", "POSSIBLE"] as const).map((t) => (
              <div key={t} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
                <span>{TIER[t].emoji}</span><b>{counts[t]}</b><span style={{ color: "var(--text-muted)" }}>{t}</span>
              </div>
            ))}
            {res.analysis?.summary && <span style={{ marginLeft: 4, fontSize: 12, padding: "3px 9px", borderRadius: 20, background: "var(--surface-2)", color: "var(--text-secondary)" }}>риск: {res.analysis.summary.risk_level}</span>}
            <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
              {(["md", "docx", "html"] as ReportFmt[]).map((f) => (
                <button key={f} onClick={() => exportReport(f)} style={{ fontSize: 12, padding: "5px 10px", borderRadius: "var(--radius)", border: "1px solid var(--border)", background: "var(--surface-1)", color: "var(--text-secondary)", cursor: "pointer" }}>
                  {f === "html" ? "🖨 PDF" : "↓ " + f.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {res.nodes.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>Граф личности (цвет узла — тир достоверности)</div>
              <Graph nodes={res.nodes} edges={res.edges} height={440} />
            </div>
          )}

          {(["CONFIRMED", "PROBABLE", "POSSIBLE"] as const).map((t) => (
            <div key={t} style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>{TIER[t].emoji} {t} ({counts[t]})</div>
              {rows(t).length === 0 ? <div style={{ color: "var(--text-muted)", fontSize: 13 }}>—</div>
                : rows(t).map((l: LedgerRow) => (
                  <div key={l.id} style={{ display: "flex", gap: 8, alignItems: "baseline", padding: "5px 0", borderBottom: "1px solid var(--border)", fontSize: 13 }}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: TIER[t].color, flexShrink: 0, alignSelf: "center" }} />
                    <span style={{ fontSize: 11, color: "var(--text-muted)", minWidth: 64 }}>{l.type}</span>
                    <span className="mono" style={{ flex: 1, minWidth: 0, wordBreak: "break-all" }}>{l.value}</span>
                    <span style={{ color: "var(--text-muted)", fontSize: 11 }}>хоп {l.hop} · {l.reason}</span>
                  </div>
                ))}
            </div>
          ))}

          {res.analysis?.risks && res.analysis.risks.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>⚠️ Риск-флаги</div>
              {res.analysis.risks.map((r, i) => (
                <div key={i} style={{ fontSize: 13, padding: "4px 0" }}>
                  <b style={{ color: r.level === "HIGH" ? "var(--danger)" : "var(--warning)" }}>{r.level}</b> {r.label} — <span style={{ color: "var(--text-secondary)" }}>{r.evidence}</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
