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
  const palette = { domain: accent, ip: "#0e8a6e", email: "#9a6700", person: "#b4231f", company: "#6d28d9", username: "#0891b2", url: "#5a6470" };
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
