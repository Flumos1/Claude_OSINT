import { useState, type FormEvent } from "react";
import { searchPerson, personReport, type PersonReq, type PersonResult } from "@/lib/api";

const COUNTRIES = [
  { code: "ua", label: "🇺🇦 UA" },
  { code: "ru", label: "🇷🇺 RU" },
  { code: "intl", label: "🌍 межд." },
];

const field: React.CSSProperties = {
  background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: "var(--radius)",
  padding: "8px 12px", color: "var(--text-primary)", fontSize: 14, outline: "none", width: "100%",
};

export default function PersonView() {
  const [f, setF] = useState<PersonReq>({ name: "", countries: ["ua", "ru", "intl"] });
  const [res, setRes] = useState<PersonResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function set<K extends keyof PersonReq>(k: K, v: PersonReq[K]) { setF((p) => ({ ...p, [k]: v })); }
  function toggleCountry(c: string) {
    setF((p) => ({ ...p, countries: p.countries.includes(c) ? p.countries.filter((x) => x !== c) : [...p.countries, c] }));
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!f.name.trim()) return;
    setLoading(true); setError(null);
    try { setRes(await searchPerson(f)); }
    catch (err) { setError(err instanceof Error ? err.message : String(err)); setRes(null); }
    finally { setLoading(false); }
  }

  async function download() {
    const md = await personReport(f);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([md], { type: "text/markdown" }));
    a.download = `${f.name.trim().replace(/\s+/g, "_") || "person"}-dossier.md`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  return (
    <div style={{ padding: 16 }}>
      <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 4 }}>Поиск физлица</div>
      <div style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 14 }}>
        Только открытые источники и при правовом основании (KYC/DD/расследование). Не для слежки за частными лицами.
      </div>

      <form onSubmit={onSubmit} style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 12, padding: 14, marginBottom: 16 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 10 }}>
          <label style={lbl}>ФИО / ПІБ *<input style={field} value={f.name} onChange={(e) => set("name", e.target.value)} placeholder="Прізвище Ім'я По-батькові" required /></label>
          <label style={lbl}>Дата рождения<input style={field} type="date" value={f.dob || ""} onChange={(e) => set("dob", e.target.value)} /></label>
          <label style={lbl}>РНОКПП / ИНН<input style={field} value={f.rnokpp || ""} onChange={(e) => set("rnokpp", e.target.value)} placeholder="10 (UA) / 12 (RU)" /></label>
          <label style={lbl}>Email<input style={field} value={f.email || ""} onChange={(e) => set("email", e.target.value)} placeholder="name@example.com" /></label>
          <label style={lbl}>Телефон<input style={field} value={f.phone || ""} onChange={(e) => set("phone", e.target.value)} placeholder="+380…" /></label>
          <label style={lbl}>Username<input style={field} value={f.username || ""} onChange={(e) => set("username", e.target.value)} placeholder="ник" /></label>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14, marginTop: 12, flexWrap: "wrap" }}>
          <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>Страны:</span>
          {COUNTRIES.map((c) => (
            <label key={c.code} style={{ fontSize: 13, display: "flex", gap: 5, alignItems: "center", cursor: "pointer" }}>
              <input type="checkbox" checked={f.countries.includes(c.code)} onChange={() => toggleCountry(c.code)} /> {c.label}
            </label>
          ))}
          <button type="submit" disabled={loading || !f.name.trim()}
            style={{ marginLeft: "auto", padding: "9px 16px", borderRadius: "var(--radius)", border: "none", cursor: "pointer", fontSize: 14, fontWeight: 500, background: "var(--accent)", color: "#fff", opacity: loading || !f.name.trim() ? 0.5 : 1 }}>
            {loading ? "…" : "Искать"}
          </button>
        </div>
      </form>

      {error && <div style={{ color: "var(--danger)", fontSize: 13, marginBottom: 12 }}>Ошибка: {error}</div>}

      {res && (
        <>
          <div style={{ background: "var(--warning-bg)", color: "var(--warning)", fontSize: 12, lineHeight: 1.5, borderRadius: "var(--radius)", padding: "10px 12px", marginBottom: 14 }}>{res.basis}</div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Варианты имени: {res.name_variants.join(", ")}</div>
            <button onClick={download} style={{ padding: "7px 13px", borderRadius: "var(--radius)", border: "1px solid var(--accent)", background: "transparent", color: "var(--accent)", cursor: "pointer", fontSize: 13 }}>↓ Досье (.md)</button>
          </div>

          <div style={{ fontSize: 12, color: "var(--text-muted)", margin: "10px 0 6px" }}>Находки</div>
          {res.findings.map((fd, i) => (
            <div key={i} style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 10, padding: "9px 12px", marginBottom: 6 }}>
              <div style={{ fontSize: 13, lineHeight: 1.5 }}>{fd.text}</div>
              <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>{fd.source}{fd.confidence ? ` · ${fd.confidence}` : ""}</div>
            </div>
          ))}

          {Object.entries(res.registries).map(([ctry, regs]) => (
            <div key={ctry} style={{ marginTop: 14 }}>
              <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 6, textTransform: "uppercase" }}>Реестры — {ctry}</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 8 }}>
                {regs.map((r, i) => (
                  <a key={i} href={r.url} target="_blank" rel="noreferrer" style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 10, padding: "9px 12px", textDecoration: "none", color: "inherit" }}>
                    <div style={{ fontSize: 13, color: "var(--accent)" }}>{r.name}</div>
                    <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 2 }}>{r.note}</div>
                  </a>
                ))}
              </div>
            </div>
          ))}

          <div style={{ fontSize: 12, color: "var(--text-muted)", margin: "16px 0 6px" }}>Правовые ограничения</div>
          {res.notes.map((n, i) => <div key={i} style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5, marginBottom: 4 }}>• {n}</div>)}
        </>
      )}
    </div>
  );
}

const lbl: React.CSSProperties = { display: "flex", flexDirection: "column", gap: 5, fontSize: 12, color: "var(--text-secondary)" };
