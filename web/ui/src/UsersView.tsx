import { useEffect, useState } from "react";
import { listUsers, createUser, type UserRow } from "@/lib/api";

export default function UsersView() {
  const [users, setUsers] = useState<UserRow[]>([]);
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  const [role, setRole] = useState("analyst");
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState("");

  function reload() { listUsers().then(setUsers).catch((e) => setError(String(e))); }
  useEffect(reload, []);

  async function add() {
    setError(null); setMsg("");
    try {
      await createUser(u, p, role);
      setMsg(`Пользователь «${u}» создан`);
      setU(""); setP("");
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div style={{ padding: 16, maxWidth: 640 }}>
      <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 14 }}>Пользователи</div>
      {error && <div style={{ color: "var(--danger)", fontSize: 13, marginBottom: 10 }}>{error}</div>}
      {msg && <div style={{ color: "var(--success)", fontSize: 13, marginBottom: 10 }}>{msg}</div>}

      <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 12, padding: 14, marginBottom: 16 }}>
        <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 10 }}>Добавить пользователя</div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input value={u} onChange={(e) => setU(e.target.value)} placeholder="логин" style={fld} />
          <input value={p} onChange={(e) => setP(e.target.value)} type="password" placeholder="пароль" style={fld} />
          <select value={role} onChange={(e) => setRole(e.target.value)} style={{ ...fld, flex: "0 0 auto" }}>
            <option value="analyst">analyst</option>
            <option value="admin">admin</option>
          </select>
          <button onClick={add} disabled={!u.trim() || !p} style={{ padding: "8px 16px", borderRadius: "var(--radius)", border: "none", background: "var(--accent)", color: "#fff", cursor: "pointer", fontSize: 14, opacity: u.trim() && p ? 1 : 0.5 }}>Создать</button>
        </div>
      </div>

      {users.map((usr) => (
        <div key={usr.username} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 10, padding: "10px 13px", marginBottom: 7 }}>
          <div style={{ fontSize: 14 }}>{usr.username}</div>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 20, background: usr.role === "admin" ? "var(--accent-bg)" : "var(--surface-2)", color: usr.role === "admin" ? "var(--accent)" : "var(--text-secondary)" }}>{usr.role}</span>
            <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{(usr.created || "").slice(0, 10)}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

const fld: React.CSSProperties = {
  flex: 1, minWidth: 120, background: "var(--surface-0)", border: "1px solid var(--border)",
  borderRadius: "var(--radius)", padding: "8px 12px", color: "var(--text-primary)", fontSize: 14, outline: "none",
};
