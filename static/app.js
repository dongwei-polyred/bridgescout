const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
let TYPES = ["brand", "artist", "movie", "tv_show", "podcast", "book", "place", "person", "video_game"];
let EXAMPLES = [];
let map;

function addRef(name = "", type = "brand") {
  const row = document.createElement("div");
  row.className = "refrow";
  row.innerHTML = `<input class="rname" placeholder="e.g. Pop Mart" value="${esc(name)}"/>
    <select class="rtype">${TYPES.map((t) => `<option ${t === type ? "selected" : ""}>${t}</option>`).join("")}</select>
    <button class="ghost" title="remove" type="button">×</button>`;
  row.querySelector("button").onclick = () => row.remove();
  $("#refs").appendChild(row);
}

function load(ex) {
  $("#brand").value = ex.brand; $("#description").value = ex.description; $("#goal").value = ex.goal;
  $("#refs").innerHTML = ""; ex.references.forEach((r) => addRef(r.name, r.type));
  $("#cities").value = ex.cities.join(", ");
}

function trace(text, cls = "") {
  const d = document.createElement("div"); d.className = cls; d.textContent = text; $("#trace").appendChild(d);
  $("#trace").scrollTop = 1e9;
}

const ev = (ids) => (Array.isArray(ids) ? ids : [ids]).filter(Boolean).map((i) => `<span class="ev" data-ev="${esc(i)}">${esc(i)}</span>`).join("");

async function run() {
  const body = {
    brand: $("#brand").value.trim(), description: $("#description").value.trim(), goal: $("#goal").value.trim(),
    references: [...document.querySelectorAll(".refrow")].map((r) => ({ name: r.querySelector(".rname").value.trim(), type: r.querySelector(".rtype").value })).filter((r) => r.name),
    cities: $("#cities").value.split(",").map((c) => c.trim()).filter(Boolean),
  };
  if (!body.references.length) { alert("Add at least one reference entity."); return; }
  $("#run").disabled = true; $("#trace").innerHTML = "";
  $("#out").innerHTML = `<div class="empty">Agent is working… watch the trace on the left.</div>`;
  try {
    const resp = await fetch("/api/brief", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
    if (!resp.ok) { const t = await resp.text(); throw new Error(t); }
    const reader = resp.body.getReader(); const dec = new TextDecoder(); let buf = "";
    while (true) {
      const { value, done } = await reader.read(); if (done) break;
      buf += dec.decode(value, { stream: true });
      let i; while ((i = buf.indexOf("\n")) >= 0) { const line = buf.slice(0, i); buf = buf.slice(i + 1); if (line.trim()) handle(JSON.parse(line)); }
    }
  } catch (e) { trace("Error: " + e.message, "warn"); }
  $("#run").disabled = false;
}

function handle(e) {
  if (e.type === "plan") trace(`planner: ${e.planner}`);
  else if (e.type === "thought") trace("💭 " + e.text);
  else if (e.type === "tool_call") trace(`→ ${e.tool}(${JSON.stringify(e.args)})`, "call");
  else if (e.type === "tool_result") trace(`  ✓ ${e.summary}`);
  else if (e.type === "warning") trace("⚠ " + e.message, "warn");
  else if (e.type === "error") { trace("✗ " + e.message, "warn"); $("#out").innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
  else if (e.type === "brief") render(e.brief);
}

function render(b) {
  const lead = b.lead_market;
  const max = Math.max(...b.markets.map((m) => m.score || 0), 1);
  const city = lead && lead.city;
  const partners = (city && b.partners[city]) || {};
  const card = (k, title) => partners[k] && partners[k].length ? `<div class="card"><div class="k">${title} ${ev(partners[k][0].evidence)}</div><ul>${partners[k].map((p) => `<li>${esc(p.name)} <small style="color:var(--mut)">${p.affinity != null ? (p.affinity * 100).toFixed(0) : ""}</small></li>`).join("")}</ul></div>` : "";
  const age = b.audience.age || {}; const ageMax = Math.max(...Object.values(age).map(Math.abs), 0.01);
  $("#out").innerHTML = `
    <div class="headline">${esc(b.headline)}</div>
    <div class="sub">${b.mode === "demo" ? "⚠ demo data · " : "Live Qloo data · "}planner: ${esc(b.planner)} · ${b.evidence.length} Qloo requests · references: ${b.references.map((r) => esc(r.name)).join(", ")}</div>
    <h3>Market fit ranking</h3>
    <div class="bars">${b.markets.map((m) => `<div class="bar ${m.city === city ? "lead" : ""}"><div>${esc(m.city)}</div><div class="track"><div class="fill" style="width:${((m.score || 0) / max) * 100}%"></div></div><div>${m.score ?? "n/a"} ${ev(m.evidence[0])}</div></div>`).join("")}</div>
    <h3>Recommended moves</h3>
    <ul class="actions">${b.actions.map((a) => `<li><b>${esc(a.title)}</b> — ${esc(a.detail)} ${ev(a.evidence)}</li>`).join("")}</ul>
    ${city ? `<h3>Where in ${esc(city)}? <small style="color:var(--mut)">affinity heatmap of your reference audience</small></h3><div id="map"></div>` : ""}
    <h3>Partners in ${esc(city || "-")}</h3>
    <div class="grid">${card("place", "Stockists / venues")}${card("brand", "Co-brand candidates")}${card("artist", "Artists & creators")}${card("podcast", "Podcasts to sponsor")}</div>
    <h3>Taste DNA → messaging keywords</h3>
    <div class="chips">${b.taste_dna.map((t) => `<span>${esc(t.name)}</span>`).join("")} ${b.taste_dna[0] ? ev(b.taste_dna[0].evidence) : ""}</div>
    ${Object.keys(age).length ? `<h3>Audience skew (aggregate) ${ev(b.audience.evidence)}</h3><div class="bars">${Object.entries(age).map(([k, v]) => `<div class="bar"><div>${esc(k.replaceAll("_", " "))}</div><div class="track"><div class="fill" style="width:${Math.max(0, v) / ageMax * 100}%"></div></div><div>${(v * 100).toFixed(0)}</div></div>`).join("")}</div>` : ""}
    <h3>Launch memo <small style="color:var(--mut)">(${esc(b.narrative_source)})</small></h3>
    <pre class="narr">${esc(b.narrative)}</pre>
    <h3>Limits</h3><ul>${b.limitations.map((l) => `<li>${esc(l)}</li>`).join("")}</ul>
    <h3>Evidence — every Qloo request behind this brief</h3>
    <table class="evid">${b.evidence.map((e) => `<tr id="row-${e.id}"><td>${e.id}</td><td>${esc(e.purpose)}<br/><code>GET ${esc(e.endpoint)}?${esc(new URLSearchParams(e.params).toString())}</code></td><td>${e.result_count} results</td></tr>`).join("")}</table>`;
  document.querySelectorAll(".ev").forEach((el) => (el.onclick = () => { const r = document.getElementById("row-" + el.dataset.ev); if (r) { r.scrollIntoView({ behavior: "smooth", block: "center" }); r.classList.add("flash"); setTimeout(() => r.classList.remove("flash"), 1500); } }));
  const pts = (city && b.hotspots[city]) || [];
  if (pts.length && window.L) {
    map = L.map("map"); L.tileLayer("https://{s}.basemap.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", { attribution: "© OpenStreetMap © CARTO" }).addTo(map);
    const amax = Math.max(...pts.map((p) => p.affinity || 0), 0.01);
    const layer = L.featureGroup(pts.map((p, i) => L.circleMarker([p.lat, p.lon], { radius: 6 + 14 * (p.affinity || 0) / amax, color: i < 3 ? "#6ee7b7" : "#ffb347", fillOpacity: 0.55, weight: 1 }).bindTooltip(`#${i + 1} affinity ${(p.affinity * 100).toFixed(0)}`))).addTo(map);
    map.fitBounds(layer.getBounds().pad(0.2));
  }
}

(async function init() {
  const h = await (await fetch("/api/health")).json();
  $("#mode").textContent = `${h.mode} · ${h.planner} planner`;
  if (h.mode === "demo") $("#demo-banner").classList.remove("hidden");
  const ex = await (await fetch("/api/examples")).json();
  TYPES = ex.entity_types; EXAMPLES = ex.examples;
  EXAMPLES.forEach((e, i) => { const o = document.createElement("option"); o.value = i; o.textContent = e.brand + " — " + e.goal; $("#example").appendChild(o); });
  $("#example").onchange = (e) => e.target.value !== "" && load(EXAMPLES[+e.target.value]);
  load(EXAMPLES[0]);
  $("#add-ref").onclick = () => addRef();
  $("#run").onclick = run;
  const q = new URLSearchParams(location.search);
  if (q.has("example")) load(EXAMPLES[+q.get("example")] || EXAMPLES[0]);
  if (q.has("autorun")) run();
})();
