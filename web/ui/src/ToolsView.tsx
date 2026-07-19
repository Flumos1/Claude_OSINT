import { useEffect, useState } from "react";
import { fetchTools, fetchCurated, type ToolsResponse, type CuratedTool } from "@/lib/api";

export default function ToolsView() {
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [flagged, setFlagged] = useState(false);
  const [data, setData] = useState<ToolsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [curated, setCurated] = useState<CuratedTool[]>([]);
  const [copied, setCopied] = useState("");

  useEffect(() => { fetchCurated().then((c) => setCurated(c.tools)).catch(() => setCurated([])); }, []);

  function copy(cmd: string, id: string) {
    navigator.clipboard?.writeText(cmd).then(() => {
      setCopied(id);
      setTimeout(() => setCopied(""), 1200);
    });
  }

  useEffect(() => {
    setLoading(true);
    const t = setTimeout(() => {
      fetchTools({ q, category, flagged, limit: 80 })
        .then(setData)
        .catch(() => setData(null))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(t);
  }, [q, category, flagged]);

  return (
    <div style={{ padding: 16 }}>
      <div style={{ marginBottom: 6, fontSize: 18, fontWeight: 600 }}>Инструменты</div>
      <div style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 14 }}>
        Индекс awesome-osint{data ? `: ${data.all_total} инструментов, ${data.flagged_total} с пометкой` : ""}.
        Наличие в списке ≠ одобрение — сверяйся с ethics-legal.
      </div>

      {curated.length > 0 && (
        <div style={{ marginBottom: 22 }}>
          <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 8 }}>★ Рабочие лошадки — с install-подсказкой</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 10 }}>
            {curated.map((t) => (
              <div key={t.id} style={{ background: "var(--surface-1)", border: t.builtin ? "1px solid var(--success, #2ea043)" : "1px solid var(--border-strong)", borderRadius: 12, padding: "12px 14px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                  <a href={t.url} target="_blank" rel="noreferrer" style={{ fontSize: 14, fontWeight: 500, color: "var(--accent)", textDecoration: "none" }}>{t.name}</a>
                  <span style={{ fontSize: 10, padding: "2px 7px", borderRadius: 20,
                    background: t.builtin ? "var(--success-bg, #12261b)" : "var(--surface-2)",
                    color: t.builtin ? "var(--success, #2ea043)" : "var(--text-secondary)" }}>
                    {t.builtin ? "✓ встроено" : t.method}
                  </span>
                </div>
                {t.note && <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5, margin: "4px 0 7px" }}>{t.note}</div>}
                {t.builtin ? (
                  <div style={{ fontSize: 11, color: "var(--success, #2ea043)", padding: "6px 8px" }}>
                    Работает автоматически — не нужна установка. Просто введи email в «Обогащение».
                  </div>
                ) : (
                  <div onClick={() => copy(t.install, t.id)} title="Скопировать"
                    className="mono"
                    style={{ fontSize: 11, background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 6, padding: "6px 8px", color: "var(--text-primary)", cursor: "pointer", wordBreak: "break-all" }}>
                    {copied === t.id ? "✓ скопировано" : `$ ${t.install}`}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 8 }}>Полный индекс</div>
      <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Поиск по названию или описанию…"
          style={{ flex: 1, minWidth: 220, background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "8px 12px", color: "var(--text-primary)", fontSize: 14, outline: "none" }} />
        <select value={category} onChange={(e) => setCategory(e.target.value)}
          style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "8px 12px", color: "var(--text-primary)", fontSize: 13, maxWidth: 260 }}>
          <option value="">Все категории{data ? ` (${data.all_total})` : ""}</option>
          {data?.categories.map((c) => (
            <option key={c.name} value={c.name}>{c.name} ({c.count})</option>
          ))}
        </select>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "var(--text-secondary)", cursor: "pointer" }}>
          <input type="checkbox" checked={flagged} onChange={(e) => setFlagged(e.target.checked)} /> только с пометкой
        </label>
      </div>

      {loading && <div style={{ color: "var(--text-muted)", fontSize: 13 }}>Загрузка…</div>}

      {data && (
        <>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>
            Найдено: {data.total}{data.total > data.items.length ? ` (показано ${data.items.length})` : ""}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 10 }}>
            {data.items.map((t, i) => (
              <a key={t.url + i} href={t.url} target="_blank" rel="noreferrer"
                style={{ display: "block", background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 12, padding: "12px 14px", textDecoration: "none", color: "inherit" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start", gap: 8 }}>
                  <div style={{ fontSize: 14, fontWeight: 500, color: "var(--accent)" }}>{t.name}</div>
                  {t.flag && (
                    <span title={t.flag} style={{ flexShrink: 0, fontSize: 10, padding: "2px 7px", borderRadius: 20, background: "var(--warning-bg)", color: "var(--warning)" }}>⚠ внимание</span>
                  )}
                </div>
                <div style={{ fontSize: 11, color: "var(--text-muted)", margin: "2px 0 6px" }}>{t.category}</div>
                {t.desc && <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>{t.desc}</div>}
                {t.flag && <div style={{ fontSize: 11, color: "var(--warning)", marginTop: 6 }}>⚠ {t.flag} — см. ethics-legal</div>}
              </a>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
