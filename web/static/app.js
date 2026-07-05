/* Claude OSINT — фронтенд SPA. Чистый ванильный JS, без сборки. */
"use strict";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const linkify = (s) => esc(s).replace(/(https?:\/\/[^\s)]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');

const state = { meta: null, lastGraph: null, network: null };

/* ---------- API ---------- */
const api = {
  meta: () => fetch("/api/meta").then(r => r.json()),
  enrich: (body) => fetch("/api/enrich", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then(async r => { if (!r.ok) throw new Error((await r.json()).detail || r.statusText); return r.json(); }),
  person: (body) => fetch("/api/person", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then(async r => { if (!r.ok) throw new Error((await r.json()).detail || r.statusText); return r.json(); }),
  recon: (body) => fetch("/api/recon", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then(async r => { if (!r.ok) throw new Error((await r.json()).detail || r.statusText); return r.json(); }),
  source: (code) => fetch(`/api/sources/${code}`).then(r => r.json()),
  skills: () => fetch("/api/skills").then(r => r.json()),
  cases: () => fetch("/api/cases").then(r => r.json()),
};

/* ---------- Router ---------- */
const views = {};
function show(view) {
  $$(".nav-item").forEach(n => n.classList.toggle("active", n.dataset.view === view));
  const content = $("#content");
  content.innerHTML = "";
  const tpl = $(`#tpl-${view}`);
  content.appendChild(tpl.content.cloneNode(true));
  (views[view] || (() => {}))();
  location.hash = view;
}

/* ---------- Dashboard ---------- */
views.dashboard = () => {
  const c = state.meta.counts;
  const stats = [
    ["enrichers", "Энричеры"], ["entity_types", "Типы сущностей"], ["countries", "Страны"],
    ["skills", "Скилы"], ["cases", "Кейсы"], ["tools", "Инструменты"],
  ];
  $("#stats").innerHTML = stats.map(([k, l]) =>
    `<div class="stat"><div class="num">${c[k] ?? 0}</div><div class="lbl">${l}</div></div>`).join("");

  $$(".chip[data-quick]").forEach(ch => ch.onclick = () => {
    const [type, country, value] = ch.dataset.quick.split("|");
    runEnrich(type, value, country || "ua", true);
  });

  const map = $("#enricher-map");
  map.innerHTML = "";
  for (const [type, list] of Object.entries(state.meta.enrichers)) {
    const row = el("div", "emap-row");
    row.innerHTML = `<div class="emap-type">${esc(type)}</div>`;
    const ls = el("div", "emap-list");
    list.forEach(e => ls.appendChild(el("span", "badge" + (e.country === "ua" ? " ua" : ""),
      esc(e.name) + (e.country ? ` ·${esc(e.country)}` : ""))));
    row.appendChild(ls);
    map.appendChild(row);
  }
};

/* ---------- Enrich ---------- */
views.enrich = () => {
  if (state.lastGraph) renderResult(state.lastGraph);
  $$("#result-tabs .tab").forEach(t => t.onclick = () => switchTab(t.dataset.tab));
};

function switchTab(tab) {
  $$("#result-tabs .tab").forEach(t => t.classList.toggle("active", t.dataset.tab === tab));
  $$("#result-body .tabpane").forEach(p => p.hidden = p.dataset.pane !== tab);
  if (tab === "graph" && state.lastGraph) drawGraph(state.lastGraph);
}

async function runEnrich(type, value, country, navigate) {
  if (navigate) show("enrich");
  const empty = $("#result-empty"); if (empty) empty.hidden = true;
  $$("#result-body .tabpane").forEach(p => p.hidden = p.dataset.pane !== "findings");
  $$("#result-tabs .tab").forEach(t => t.classList.toggle("active", t.dataset.tab === "findings"));
  const fp = $('[data-pane="findings"]');
  $("#result-title").textContent = `${type}: ${value}`;
  fp.innerHTML = `<div class="loading"><span class="spin">◴</span> Запуск энричеров…</div>`;
  try {
    const g = await api.enrich({ type, value, country });
    state.lastGraph = g;
    renderResult(g);
  } catch (e) {
    fp.innerHTML = `<div class="finding"><span class="f-tag ERROR">ERROR</span><div class="f-main">${esc(e.message)}</div></div>`;
  }
}

function renderResult(g) {
  $("#result-title").textContent = `${g.input.type}: ${g.input.value}` + (g.input.country ? ` [${g.input.country}]` : "");
  const empty = $("#result-empty"); if (empty) empty.hidden = true;

  // Findings
  const fp = $('[data-pane="findings"]');
  if (!g.findings.length) fp.innerHTML = `<div class="loading">Энричеров для этого типа/страны не нашлось.</div>`;
  else fp.innerHTML = `<div style="margin-bottom:12px" class="muted">Энричеры: ${g.enrichers_run.map(esc).join(", ") || "—"}</div>` +
    g.findings.map(f => `
      <div class="finding">
        <span class="f-tag ${esc(f.label)}">${esc(f.label)}</span>
        <div class="f-main">
          <div class="f-text">${linkify(f.text)}</div>
          <div class="f-meta">${esc(f.source)}${f.confidence ? ` · <span class="f-conf">${esc(f.confidence)}</span>` : ""}</div>
        </div>
      </div>`).join("");

  // Nodes
  const np = $('[data-pane="nodes"]');
  np.innerHTML = `<table class="tbl"><thead><tr><th>Тип</th><th>Значение</th><th>Атрибуты</th></tr></thead><tbody>` +
    g.nodes.map(n => `<tr><td><span class="tag-type">${esc(n.type)}</span></td><td class="mono">${esc(n.value)}</td>
      <td class="muted">${esc(Object.entries(n.attrs || {}).filter(([, v]) => v).map(([k, v]) => `${k}=${v}`).join("  ")) || "—"}</td></tr>`).join("") +
    `</tbody></table><div class="muted" style="margin-top:10px">Узлов: ${g.nodes.length} · Связей: ${g.edges.length}</div>`;

  // JSON
  $("#json-out").textContent = JSON.stringify(g, null, 2);
}

function drawGraph(g) {
  const host = $("#graph");
  if (!host) return;
  if (typeof vis === "undefined") { host.innerHTML = `<div class="loading">Граф-движок не загрузился (нет сети). Смотри вкладки «Сущности» / «JSON».</div>`; return; }
  const cs = getComputedStyle(document.body);
  const accent = cs.getPropertyValue("--accent").trim();
  const text = cs.getPropertyValue("--text").trim();
  const border = cs.getPropertyValue("--border-strong").trim();
  const panel = cs.getPropertyValue("--bg").trim();
  const palette = { domain: accent, ip: "#0e8a6e", email: "#9a6700", person: "#b4231f", company: "#6d28d9", username: "#0891b2", url: "#5a6470", aircraft: "#0369a1", airport: "#0e7490", vessel: "#1e6091" };
  const nodes = g.nodes.map(n => ({
    id: n.id, label: `${n.value}`, group: n.type,
    color: { background: panel, border: palette[n.type] || border, highlight: { background: panel, border: accent } },
    font: { color: text, face: "Inter", size: 13 }, shape: "box",
    margin: 8, borderWidth: 2,
  }));
  const edges = g.edges.map(e => ({ from: e.source, to: e.target, label: e.rel, arrows: "to",
    color: { color: border, highlight: accent }, font: { color: cs.getPropertyValue("--text-faint").trim(), size: 10, strokeWidth: 0 } }));
  if (state.network) state.network.destroy();
  state.network = new vis.Network(host, { nodes, edges }, {
    physics: { stabilization: true, barnesHut: { springLength: 130, gravitationalConstant: -6000 } },
    interaction: { hover: true }, nodes: { shapeProperties: { borderRadius: 6 } },
  });
}

/* ---------- Person search ---------- */
views.person = () => {
  $("#person-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = {
      name: $("#p-name").value.trim(),
      dob: $("#p-dob").value || null,
      rnokpp: $("#p-rnokpp").value.trim() || null,
      email: $("#p-email").value.trim() || null,
      phone: $("#p-phone").value.trim() || null,
      username: $("#p-username").value.trim() || null,
      countries: $$(".pform-countries .cb input:checked").map(c => c.value),
    };
    if (!body.name) return;
    state.lastPersonQuery = body;
    const out = $("#person-result");
    out.innerHTML = `<div class="panel"><div class="panel-body loading"><span class="spin">◴</span> Поиск по реестрам…</div></div>`;
    try { renderDossier(await api.person(body)); }
    catch (err) { out.innerHTML = `<div class="panel"><div class="panel-body"><span class="f-tag ERROR">ERROR</span> ${esc(err.message)}</div></div>`; }
  });
};

async function downloadReport() {
  if (!state.lastPersonQuery) return;
  const r = await fetch("/api/person/report", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(state.lastPersonQuery) });
  const { markdown } = await r.json();
  const blob = new Blob([markdown], { type: "text/markdown" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `dossier-${(state.lastPersonQuery.name || "person").replace(/\s+/g, "_")}.md`;
  a.click(); URL.revokeObjectURL(a.href);
}

function renderDossier(d) {
  $("#basis-bar").textContent = d.basis;
  const out = $("#person-result");
  const findings = d.findings.map(f => `
    <div class="finding"><span class="f-tag ${esc(f.label)}">${esc(f.label)}</span>
      <div class="f-main"><div class="f-text">${linkify(f.text)}</div>
        <div class="f-meta">${esc(f.source)}${f.confidence ? ` · <span class="f-conf">${esc(f.confidence)}</span>` : ""}</div></div></div>`).join("");
  const regs = Object.entries(d.registries).map(([c, items]) => `
    <div class="reg-group"><h3>${c === "ua" ? "🇺🇦 Украина" : c === "ru" ? "🇷🇺 Россия" : "🌍 Международные"}</h3>
      ${items.map(r => `<div class="reg-item"><span class="reg-name"><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.name)}</a></span><span class="reg-note">${esc(r.note)}</span></div>`).join("")}</div>`).join("");
  out.innerHTML = `
    <div class="panel dossier-section"><div class="panel-head"><h2>Варианты написания (recall)</h2>
      <button class="btn" id="dl-report" type="button">↓ Отчёт (.md)</button></div>
      <div class="panel-body variants">${d.name_variants.map(v => `<span class="badge">${esc(v)}</span>`).join("")}</div></div>
    <div class="panel dossier-section"><div class="panel-head"><h2>Находки (живые источники)</h2></div>
      <div class="panel-body">${findings || '<span class="muted">Прямых находок нет — используй ссылки на реестры ниже.</span>'}</div></div>
    <div class="panel dossier-section"><div class="panel-head"><h2>Граф связей</h2></div>
      <div class="panel-body"><div id="graph"></div></div></div>
    <div class="panel dossier-section"><div class="panel-head"><h2>Реестры (точки входа)</h2></div>
      <div class="panel-body">${regs}</div></div>
    <div class="panel dossier-section"><div class="panel-head"><h2>Правовые ограничения</h2></div>
      <div class="panel-body"><ul class="notes-list">${d.notes.map(n => `<li>${esc(n)}</li>`).join("")}</ul></div></div>`;
  $("#dl-report")?.addEventListener("click", downloadReport);
  drawGraph(d);
}

/* ---------- Recon-граф ---------- */
const TIER = {
  CONFIRMED: { color: "#1a7f37", emoji: "🟢", label: "CONFIRMED" },
  PROBABLE: { color: "#9a6700", emoji: "🟡", label: "PROBABLE" },
  POSSIBLE: { color: "#8b95a1", emoji: "⚪", label: "POSSIBLE" },
};

views.recon = () => {
  $("#recon-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = {
      basis: $("#r-basis").value.trim(),
      name: $("#r-name").value.trim() || null,
      email: $("#r-email").value.trim(),
      username: $("#r-username").value.trim(),
      github: $("#r-github").value.trim(),
      phone: $("#r-phone").value.trim(),
      hops: parseInt($("#r-hops").value, 10) || 2,
    };
    if (!body.basis) { $("#recon-basis-warn").classList.add("warn-flash"); return; }
    const out = $("#recon-result");
    out.innerHTML = `<div class="panel"><div class="panel-body loading"><span class="spin">◴</span> Многошаговый пивотинг и корреляция…</div></div>`;
    try { renderRecon(await api.recon(body)); }
    catch (err) { out.innerHTML = `<div class="panel"><div class="panel-body"><span class="f-tag ERROR">ERROR</span> ${esc(err.message)}</div></div>`; }
  });
};

function renderRecon(d) {
  state.lastRecon = d;
  const tierOf = {};
  (d.ledger || []).forEach(l => { tierOf[l.id] = l; });
  const an = d.analysis || {}, tl = d.timeline || {};
  const counts = { CONFIRMED: 0, PROBABLE: 0, POSSIBLE: 0 };
  (d.ledger || []).forEach(l => counts[l.tier]++);

  const ledgerRows = (tier) => (d.ledger || []).filter(l => l.tier === tier).map(l =>
    `<div class="ledger-row"><span class="tier-dot" style="background:${TIER[tier].color}"></span>
       <span class="tag-type">${esc(l.type)}</span>
       <span class="mono">${esc(l.value)}</span>
       <span class="muted">хоп ${l.hop} · ${esc(l.reason)}</span></div>`).join("") || `<div class="muted" style="padding:6px 0">—</div>`;

  const riskBadge = an.summary ? `<span class="risk-badge ${an.summary.risk_level}">риск: ${an.summary.risk_level}</span>` : "";
  const risks = (an.risks || []).map(r => `<li><span class="risk-badge ${r.level}">${r.level}</span> <b>${esc(r.label)}</b> — ${esc(r.evidence)}</li>`).join("");
  const insights = (an.insights || []).map(i => `<li><span class="f-tag ${esc(i.label)}">${esc(i.label)}</span> ${esc(i.text)}</li>`).join("");
  const timeline = (tl.events || []).slice(0, 14).map(e => `<li><b class="mono">${esc(e.date)}</b> — ${esc(e.what)}</li>`).join("");
  const anomalies = (tl.anomalies || []).map(a => `<li class="anomaly">⚑ ${esc(a)}</li>`).join("");

  $("#recon-result").innerHTML = `
    <div class="tier-summary">
      ${["CONFIRMED", "PROBABLE", "POSSIBLE"].map(t =>
        `<div class="tier-card"><span class="tier-emoji">${TIER[t].emoji}</span><b>${counts[t]}</b><span>${t}</span></div>`).join("")}
      <div class="tier-card">${riskBadge}<span>узлов ${d.nodes.length} · связей ${d.edges.length}</span></div>
    </div>
    <div class="panel dossier-section"><div class="panel-head"><h2>Граф личности (цвет = достоверность связи)</h2></div>
      <div class="panel-body"><div id="graph"></div>
        <div class="graph-legend">${["CONFIRMED", "PROBABLE", "POSSIBLE"].map(t => `<span><i style="background:${TIER[t].color}"></i>${t}</span>`).join("")}</div></div></div>
    ${risks ? `<div class="panel dossier-section"><div class="panel-head"><h2>⚠️ Риск-флаги</h2></div><div class="panel-body"><ul class="notes-list">${risks}</ul></div></div>` : ""}
    ${insights ? `<div class="panel dossier-section"><div class="panel-head"><h2>🧠 Выводы и гипотезы</h2></div><div class="panel-body"><ul class="notes-list">${insights}</ul></div></div>` : ""}
    <div class="grid-2">
      <div class="panel dossier-section"><div class="panel-head"><h2>🟢 CONFIRMED (${counts.CONFIRMED})</h2></div><div class="panel-body">${ledgerRows("CONFIRMED")}</div></div>
      <div class="panel dossier-section"><div class="panel-head"><h2>🟡 PROBABLE (${counts.PROBABLE})</h2></div><div class="panel-body">${ledgerRows("PROBABLE")}</div></div>
    </div>
    <div class="panel dossier-section"><div class="panel-head"><h2>⚪ POSSIBLE (${counts.POSSIBLE}) — проверяй вручную</h2></div><div class="panel-body">${ledgerRows("POSSIBLE")}</div></div>
    ${timeline ? `<div class="panel dossier-section"><div class="panel-head"><h2>🗓️ Таймлайн</h2></div><div class="panel-body"><ul class="notes-list">${timeline}${anomalies}</ul></div></div>` : ""}`;

  drawReconGraph(d, tierOf);
}

function drawReconGraph(d, tierOf) {
  const host = $("#graph");
  if (!host || typeof vis === "undefined") { if (host) host.innerHTML = `<div class="loading">Граф-движок не загрузился.</div>`; return; }
  const cs = getComputedStyle(document.body);
  const text = cs.getPropertyValue("--text").trim();
  const border = cs.getPropertyValue("--border-strong").trim();
  const panel = cs.getPropertyValue("--bg").trim();
  const nodes = d.nodes.map(n => {
    const t = tierOf[n.id]; const tier = t ? t.tier : (n.hop === 0 ? "CONFIRMED" : "POSSIBLE");
    const col = TIER[tier].color;
    return { id: n.id, label: n.value, shape: n.type === "person" ? "ellipse" : "box",
      color: { background: panel, border: col, highlight: { background: panel, border: col } },
      borderWidth: n.hop === 0 ? 4 : 2, font: { color: text, face: "Inter", size: 13 }, margin: 8,
      title: `${n.type} · ${tier}${t ? " · " + t.reason : ""}` };
  });
  const edges = d.edges.map(e => ({ from: e.source, to: e.target, label: e.rel, arrows: "to",
    color: { color: border }, font: { color: cs.getPropertyValue("--text-faint").trim(), size: 10, strokeWidth: 0 } }));
  if (state.network) state.network.destroy();
  state.network = new vis.Network(host, { nodes, edges }, {
    physics: { stabilization: true, barnesHut: { springLength: 140, gravitationalConstant: -7000 } },
    interaction: { hover: true }, nodes: { shapeProperties: { borderRadius: 6 } },
  });
}

/* ---------- Sources ---------- */
views.sources = () => {
  const tabs = $("#source-tabs");
  tabs.innerHTML = "";
  state.meta.countries.forEach((c, i) => {
    const b = el("button", "source-tab" + (i === 0 ? " active" : ""), `${c.flag} ${esc(c.name)}`);
    b.onclick = () => { $$(".source-tab").forEach(t => t.classList.remove("active")); b.classList.add("active"); loadSource(c.code); };
    tabs.appendChild(b);
  });
  if (state.meta.countries[0]) loadSource(state.meta.countries[0].code);
};
async function loadSource(code) {
  const box = $("#source-content");
  box.innerHTML = `<div class="loading"><span class="spin">◴</span> Загрузка…</div>`;
  try { box.innerHTML = (await api.source(code)).html; } catch { box.innerHTML = `<div class="loading">Не удалось загрузить.</div>`; }
}

/* ---------- Skills / Cases ---------- */
views.skills = async () => {
  const list = $("#skills-list");
  list.innerHTML = `<div class="loading"><span class="spin">◴</span> Загрузка…</div>`;
  const sk = await api.skills();
  list.innerHTML = sk.map(s => `<div class="card"><h3>◇ ${esc(s.name)}</h3><p>${esc(s.description)}</p></div>`).join("");
};
views.cases = async () => {
  const list = $("#cases-list");
  const cs = await api.cases();
  list.innerHTML = cs.length ? cs.map(c => `<div class="card"><h3>▥ ${esc(c.slug)}</h3><p>${esc((c.brief || "").slice(0, 200))}</p></div>`).join("")
    : `<div class="card"><h3>Кейсов нет</h3><p>Заведи первый кейс копией <code>cases/_TEMPLATE</code> — Claude сделает это по запросу.</p></div>`;
};

/* ---------- Boot ---------- */
function fillSelectors() {
  const t = $("#g-type"); t.innerHTML = state.meta.entity_types.map(x => `<option value="${x}">${x}</option>`).join("");
  const c = $("#g-country");
  c.innerHTML = `<option value="">— страна —</option>` + state.meta.countries.map(x => `<option value="${x.code}"${x.code === "ua" ? " selected" : ""}>${x.flag} ${x.code}</option>`).join("");
}

$("#globalsearch").addEventListener("submit", (e) => {
  e.preventDefault();
  const type = $("#g-type").value, value = $("#g-value").value.trim(), country = $("#g-country").value || null;
  if (value) runEnrich(type, value, country, true);
});
$("#nav").addEventListener("click", e => { const it = e.target.closest(".nav-item"); if (it) show(it.dataset.view); });
$("#theme-toggle").onclick = () => {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next; localStorage.setItem("theme", next);
  if (state.lastGraph && !$('[data-pane="graph"]').hidden) drawGraph(state.lastGraph);
};

(async function boot() {
  document.documentElement.dataset.theme = localStorage.getItem("theme") || "light";
  state.meta = await api.meta();
  fillSelectors();
  show(location.hash.slice(1) || "dashboard");
})();
