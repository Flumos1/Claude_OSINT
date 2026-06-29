import { useEffect, useState } from "react";
import { fetchKeys, type KeyStatus } from "@/lib/api";

export default function SettingsView() {
  const [keys, setKeys] = useState<KeyStatus[]>([]);
  useEffect(() => { fetchKeys().then(setKeys).catch(() => setKeys([])); }, []);

  const setCount = keys.filter((k) => k.set).length;

  return (
    <div style={{ padding: 16, maxWidth: 720 }}>
      <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 4 }}>Настройки · API-ключи</div>
      <div style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 14 }}>
        Задано {setCount} из {keys.length}. Ключи задаются в <span className="mono">scripts/.env</span> (значения не показываются).
        Энричеры работают и без ключей — с лимитами/подсказками.
      </div>
      {keys.map((k) => (
        <div key={k.name} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 10, padding: "10px 13px", marginBottom: 7 }}>
          <div style={{ minWidth: 0 }}>
            <div className="mono" style={{ fontSize: 13 }}>{k.name}</div>
            <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 2 }}>{k.desc}</div>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexShrink: 0 }}>
            {!k.set && (
              <a href={k.url} target="_blank" rel="noreferrer" style={{ fontSize: 12, color: "var(--accent)", textDecoration: "none", whiteSpace: "nowrap" }}>получить ключ →</a>
            )}
            <span style={{ fontSize: 10, padding: "2px 7px", borderRadius: 20, background: "var(--surface-2)", color: "var(--text-muted)" }}>{k.tier === "free" ? "free" : "платный"}</span>
            <span style={{ fontSize: 11, padding: "2px 9px", borderRadius: 20, background: k.set ? "var(--success-bg)" : "var(--surface-2)", color: k.set ? "var(--success)" : "var(--text-muted)" }}>
              {k.set ? "✓ задан" : "не задан"}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
