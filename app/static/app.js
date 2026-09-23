// Fly brain explorer page. Plain JS, no build step, no outside libraries.
// FlyWire ids are 18 digits, too long for JavaScript numbers, so they are
// always kept as TEXT here and in every request to the server.
"use strict";

const $ = (id) => document.getElementById(id);
const LISTS = ["silence", "watch"];        // the Stimulate list is split into groups (state.groups)
const DEFAULT_RATE = "150";
function newGroup(name, rate) { return { name, rate: String(rate), ids: new Map() }; } // ids: id -> neuron record
const state = {
  groups: [newGroup("Group 1", DEFAULT_RATE)], active: 0,
  lists: { silence: new Map(), watch: new Map() },
  model: { fix: "none", upgrades: new Set() }, modelInfo: null,
  hits: [], hitsTotal: 0, query: "",
  job: null, pollTimer: null, lastParams: null, running: false,
  raster: null, replayFrame: null, status: null,
};

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function snapshot() { return $("snapshot").value; }
function label(n) { return n.cell_type || n.name || (n.cell_class ? n.cell_class + " (no type)" : "") || "(no cell type)"; }
function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
function totalStim() { return state.groups.reduce((a, g) => a + g.ids.size, 0); }

async function api(path, opts = {}) {
  const init = { headers: {} , ...opts };
  if (opts.json !== undefined) {
    init.method = init.method || "POST";
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(opts.json);
  }
  const r = await fetch(path, init);
  const text = await r.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = { detail: text }; }
  if (!r.ok) {
    const d = data && data.detail;
    throw new Error(typeof d === "string" ? d : JSON.stringify(d || r.statusText));
  }
  return data;
}

// ---------------- status + banner -----------------------------------------
function showBanner(text, fake) {
  const b = $("banner");
  if (!text) { b.hidden = true; return; }
  b.hidden = false;
  b.className = "banner" + (fake ? " fake" : "");
  const lead = state.status && state.status.runs_enabled === false ? "No simulator." : "Not the fly brain model.";
  b.innerHTML = fake ? `<strong>${lead}</strong> ` + esc(text) : esc(text);
}

function updateRunButton() {
  const s = state.status, m = state.modelInfo;
  const modelBad = m && (!m.ok || m.problem);
  $("runBtn").disabled = state.running || !s || !s.runs_enabled || !!modelBad;
}

async function loadStatus() {
  try {
    const s = await api("/api/status");
    const first = !state.status;
    state.status = s;
    const e = s.engine;
    const n = s.neurons[snapshot()] || Object.values(s.neurons)[0];
    $("engineLine").textContent =
      `Engine: ${e.name} (${e.version})` + (e.is_fake ? " - STAND-IN" : "") +
      (n ? ` · Neurons: ${n.count.toLocaleString()} from ${n.source}` : "");
    showBanner(s.banner, s.is_fake || !s.runs_enabled);
    if (!s.runs_enabled) $("runHint").textContent = "Runs are switched off: no working simulator (see the banner at the top).";
    if (first) renderModelOptions();
    updateRunButton();
  } catch (err) {
    $("engineLine").textContent = "Could not reach the app server.";
    showBanner("The page cannot reach the app server: " + err.message, true);
  }
}

// ---------------- model ------------------------------------------------------
function optHtml(type, name, o, checked) {
  return `<label class="opt" data-opt="${name}:${esc(o.id)}">
    <input type="${type}" name="${name}" value="${esc(o.id)}" ${checked ? "checked" : ""}>
    <span class="opt-text"><span class="opt-title">${esc(o.label)}</span>
      <a href="/api/model-docs/${encodeURIComponent(o.doc)}" target="_blank" rel="noopener" title="docs/${esc(o.doc)}">read more</a>
      <small>${esc(o.about)}</small>
      <small class="why" hidden></small></span>
  </label>`;
}

function renderModelOptions() {
  const m = state.status && state.status.models;
  if (!m) return;
  $("fixOptions").innerHTML = "<legend>Model</legend>" +
    m.fixes.map((o) => optHtml("radio", "fix", o, state.model.fix === o.id)).join("");
  $("upgradeOptions").innerHTML = "<legend>Optional upgrades</legend>" +
    m.upgrades.map((o) => optHtml("checkbox", "up", o, state.model.upgrades.has(o.id))).join("");
  refreshModel();
}

function modelQuery() {
  return `snapshot=${snapshot()}&fix=${encodeURIComponent(state.model.fix)}&upgrades=${encodeURIComponent([...state.model.upgrades].join(","))}`;
}

let modelSeq = 0;
async function refreshModel() {
  const seq = ++modelSeq;
  let r;
  try { r = await api("/api/models/state?" + modelQuery()); }
  catch (err) {
    $("modelProblem").hidden = false;
    $("modelProblem").textContent = "Could not check the model choice: " + err.message;
    return;
  }
  if (seq !== modelSeq) return;               // a newer check is on its way
  state.modelInfo = r;
  // Each option: switched off (with the reason) if it cannot be combined with the current choice.
  for (const el of document.querySelectorAll("#modelBlock label.opt")) {
    const o = r.options[el.dataset.opt];
    const input = el.querySelector("input"), why = el.querySelector(".why");
    const blocked = o && !o.allowed && !input.checked;
    input.disabled = !!blocked;
    el.classList.toggle("blocked", !!blocked);
    why.hidden = !(o && !o.allowed);
    why.textContent = o && !o.allowed ? "Not available now: " + o.why : "";
  }
  const problem = r.problem;
  $("modelProblem").hidden = !problem;
  $("modelProblem").textContent = problem ? (r.ok ? "This model cannot be used here: " : "This combination is not offered: ") + problem : "";
  $("modelState").innerHTML = r.ok && !r.problem ? modelStateText(r) : "";
  if (problem) $("runHint").textContent = "Pick another model (see section 3) before running.";
  else if ($("runHint").textContent.startsWith("Pick another model")) $("runHint").textContent = "";
  updateRunButton();
}

function modelStateText(r) {
  const m = r.memory, max = r.models.max_in_memory;
  const name = `<b>${esc(r.label)}</b>`;
  if (m.building) return `${name}: <span class="busy">being built right now</span>. It stays in memory afterwards.`;
  if (m.error) return `${name}: <span class="bad">the last attempt to build it failed: ${esc(m.error)}</span>. ` +
    "Runs with it are refused; the app never runs another model in its place. Press Run to try again.";
  if (m.in_memory) return `${name}: ready (built and in memory), so runs start straight away.`;
  let t = `${name}: not in memory yet. The first run builds it (` +
    (m.last_build_s != null ? `it took ${Math.round(m.last_build_s)} s last time` : "a few seconds to about a minute") + ").";
  if (m.other_building) t += ` Another model (${esc(m.other_building)}) is being built right now.`;
  if (m.will_drop) t += ` The app keeps at most ${max} models in memory, so it will drop ${esc(m.will_drop)} to make room.`;
  return t;
}

$("modelBlock").addEventListener("change", (ev) => {
  const t = ev.target;
  if (t.name === "fix") state.model.fix = t.value;
  else if (t.name === "up") { if (t.checked) state.model.upgrades.add(t.value); else state.model.upgrades.delete(t.value); }
  else return;
  saveDraft();
  refreshModel();
});

function setModel(v) {
  state.model.fix = (v && v.fix) || "none";
  state.model.upgrades = new Set((v && v.upgrades) || []);
  for (const el of document.querySelectorAll("#modelBlock input")) {
    el.checked = el.name === "fix" ? el.value === state.model.fix : state.model.upgrades.has(el.value);
  }
  refreshModel();
}

// ---------------- search ---------------------------------------------------
let searchTimer = null;
$("q").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(runSearch, 200);
});

async function runSearch(limit = 50) {
  const q = $("q").value.trim();
  state.query = q;
  if (q.length < 2) {
    state.hits = []; state.hitsTotal = 0; renderHits();
    $("searchInfo").textContent = "Type at least 2 characters.";
    return;
  }
  try {
    const r = await api(`/api/neurons/search?q=${encodeURIComponent(q)}&limit=${limit}&snapshot=${snapshot()}`);
    if (r.query !== $("q").value.trim()) return; // a newer search is on its way
    state.hits = r.results; state.hitsTotal = r.total;
    $("searchInfo").textContent = r.total === 0 ? "No neurons match."
      : `${r.total.toLocaleString()} match${r.total === 1 ? "" : "es"}` + (r.total > r.results.length ? `, showing the first ${r.results.length}.` : ".");
    renderHits();
  } catch (err) {
    $("searchInfo").textContent = "Search failed: " + err.message;
  }
}

function renderHits() {
  const ul = $("hits");
  ul.innerHTML = state.hits.map((n, i) => `
    <li>
      <div class="hit-text"><b>${esc(label(n))}</b> ${esc(n.super_class)}${n.side ? " · " + esc(n.side) : ""}${n.nt ? " · " + esc(n.nt) : ""}
        <small>${esc(n.root_id)}</small></div>
      <div class="hit-actions">
        <button type="button" class="small" data-add="excite" data-i="${i}" title="Stimulate (adds to the group marked 'add here')">Stim</button>
        <button type="button" class="small" data-add="silence" data-i="${i}" title="Silence">Silence</button>
        <button type="button" class="small" data-add="watch" data-i="${i}" title="Watch">Watch</button>
      </div>
    </li>`).join("");
  const bulk = $("bulk");
  bulk.hidden = !(state.hitsTotal > 1 && state.hitsTotal <= 5000);
  $("bulkText").textContent = `All ${state.hitsTotal.toLocaleString()} matches:`;
}

$("hits").addEventListener("click", (ev) => {
  const b = ev.target.closest("button[data-add]");
  if (!b) return;
  addTo(b.dataset.add, [state.hits[+b.dataset.i]]);
});

$("bulk").addEventListener("click", async (ev) => {
  const b = ev.target.closest("button[data-bulk]");
  if (!b) return;
  try {
    const r = await api(`/api/neurons/search?q=${encodeURIComponent(state.query)}&limit=5000&snapshot=${snapshot()}`);
    addTo(b.dataset.bulk, r.results);
  } catch (err) { $("searchInfo").textContent = "Could not add them: " + err.message; }
});

// ---------------- pick lists and stimulus groups ------------------------------
function addTo(list, neurons) {
  for (const n of neurons) {
    // A neuron can be stimulated (in one group) or silenced, not both.
    if (list === "excite") {
      state.lists.silence.delete(n.root_id);
      state.groups.forEach((g, i) => { if (i !== state.active) g.ids.delete(n.root_id); });
      state.groups[state.active].ids.set(n.root_id, n);
    } else {
      if (list === "silence") for (const g of state.groups) g.ids.delete(n.root_id);
      state.lists[list].set(n.root_id, n);
    }
  }
  renderLists();
}

function listOf(key) { return key.startsWith("g:") ? state.groups[+key.slice(2)].ids : state.lists[key]; }

function chipHtml(n, key) {
  return `<li class="${n.known === false ? "unknown" : ""}" title="${esc(n.root_id)}${n.known === false ? " (not in the neuron table)" : ""}">
    <span>${esc(label(n))} ${esc(n.root_id.slice(-6))}</span>
    <button type="button" aria-label="Remove" data-remove="${key}" data-id="${esc(n.root_id)}">&times;</button>
  </li>`;
}

function renderGroups() {
  const multi = state.groups.length > 1;
  $("groups").innerHTML = state.groups.map((g, i) => `
    <div class="group${i === state.active ? " active" : ""}" data-g="${i}">
      <div class="group-head">
        <label class="here" title="New picks from the search go into this group">
          <input type="radio" name="activeGroup" value="${i}" ${i === state.active ? "checked" : ""}> add here</label>
        <input class="gname" type="text" maxlength="40" value="${esc(g.name)}" aria-label="Name of stimulus group ${i + 1}" data-gname="${i}">
        <label class="grate"><input type="number" min="0" max="1000" step="1" value="${esc(g.rate)}"
          aria-label="Input rate of stimulus group ${i + 1}, in Hz" data-grate="${i}"><span>Hz</span></label>
        <span class="count">${g.ids.size}</span>
        <button type="button" class="link" data-gclear="${i}">Clear</button>
        ${multi ? `<button type="button" class="gx" aria-label="Remove stimulus group ${i + 1}" title="Remove this group" data-gremove="${i}">&times;</button>` : ""}
      </div>
      <ul class="chips">${[...g.ids.values()].map((n) => chipHtml(n, "g:" + i)).join("")}</ul>
    </div>`).join("");
}

function renderLists() {
  renderGroups();
  $("n-excite").textContent = totalStim();
  for (const k of LISTS) {
    const m = state.lists[k];
    $("n-" + k).textContent = m.size;
    $("list-" + k).innerHTML = [...m.values()].map((n) => chipHtml(n, k)).join("");
  }
  const hint = $("runHint").textContent;
  if (!totalStim()) $("runHint").textContent = "Add at least one neuron to Stimulate.";
  else if (hint === "Add at least one neuron to Stimulate.") $("runHint").textContent = "";
  saveDraft();
}

document.addEventListener("click", (ev) => {
  const rm = ev.target.closest("button[data-remove]");
  if (rm) { listOf(rm.dataset.remove).delete(rm.dataset.id); renderLists(); }
  const cl = ev.target.closest("button[data-clear]");
  if (cl) { state.lists[cl.dataset.clear].clear(); renderLists(); }
  const gc = ev.target.closest("button[data-gclear]");
  if (gc) { state.groups[+gc.dataset.gclear].ids.clear(); renderLists(); }
  const gr = ev.target.closest("button[data-gremove]");
  if (gr) {
    const i = +gr.dataset.gremove;
    state.groups.splice(i, 1);
    if (state.active >= state.groups.length || state.active === i) state.active = 0;
    else if (state.active > i) state.active -= 1;
    renderLists();
  }
});

$("addGroup").addEventListener("click", () => {
  if (state.groups.length >= 8) { $("runHint").textContent = "At most 8 stimulus groups."; return; }
  const last = state.groups[state.groups.length - 1];
  state.groups.push(newGroup(`Group ${state.groups.length + 1}`, last ? last.rate : DEFAULT_RATE));
  state.active = state.groups.length - 1;
  renderLists();
  const inp = document.querySelector(`[data-gname="${state.active}"]`);
  if (inp) { inp.focus(); inp.select(); }
});

// Typing a group's name or rate updates the state without redrawing (keeps the cursor).
$("groups").addEventListener("input", (ev) => {
  const t = ev.target;
  if (t.dataset.gname !== undefined) state.groups[+t.dataset.gname].name = t.value;
  else if (t.dataset.grate !== undefined) state.groups[+t.dataset.grate].rate = t.value;
  else return;
  saveDraft();
});
$("groups").addEventListener("change", (ev) => {
  const t = ev.target;
  if (t.name !== "activeGroup") return;
  state.active = +t.value;
  for (const el of document.querySelectorAll("#groups .group")) el.classList.toggle("active", +el.dataset.g === state.active);
  saveDraft();
});

function saveDraft() {
  try {
    localStorage.setItem("flybrain-draft", JSON.stringify({
      v: 2,
      groups: state.groups.map((g) => ({ name: g.name, rate: g.rate, neurons: [...g.ids.values()] })),
      active: state.active,
      lists: Object.fromEntries(LISTS.map((k) => [k, [...state.lists[k].values()]])),
      duration: $("duration").value, trials: $("trials").value, seed: $("seed").value,
      snapshot: snapshot(), model: { fix: state.model.fix, upgrades: [...state.model.upgrades] },
    }));
  } catch { /* storage blocked: the page still works, the draft just is not kept */ }
}
function loadDraft() {
  try {
    const d = JSON.parse(localStorage.getItem("flybrain-draft") || "null");
    if (!d) return;
    if (Array.isArray(d.groups) && d.groups.length) {
      state.groups = d.groups.map((g, i) => {
        const ng = newGroup(g.name || `Group ${i + 1}`, g.rate ?? DEFAULT_RATE);
        for (const n of g.neurons || []) ng.ids.set(n.root_id, n);
        return ng;
      });
      state.active = Math.min(Math.max(0, d.active | 0), state.groups.length - 1);
    } else if (d.lists && d.lists.excite) {         // a draft from before stimulus groups existed
      const g = newGroup("Group 1", d.rate || DEFAULT_RATE);
      for (const n of d.lists.excite) g.ids.set(n.root_id, n);
      state.groups = [g];
    }
    for (const k of LISTS) for (const n of (d.lists && d.lists[k]) || []) state.lists[k].set(n.root_id, n);
    for (const k of ["duration", "trials", "seed", "snapshot"]) if (d[k] !== undefined) $(k).value = d[k];
    if (d.model) { state.model.fix = d.model.fix || "none"; state.model.upgrades = new Set(d.model.upgrades || []); }
  } catch { /* ignore a broken or blocked draft */ }
}
for (const k of ["duration", "trials", "seed"]) $(k).addEventListener("change", saveDraft);

// ---------------- running ------------------------------------------------
function currentParams() {
  const seed = $("seed").value.trim();
  return {
    stim_groups: state.groups.map((g) => ({ name: g.name.trim(), rate_hz: g.rate === "" ? null : Number(g.rate), ids: [...g.ids.keys()] })),
    silence: [...state.lists.silence.keys()], watch: [...state.lists.watch.keys()],
    duration_ms: Number($("duration").value), n_trials: Number($("trials").value),
    seed: seed === "" ? null : Number(seed),
    snapshot: snapshot(), variant: { fix: state.model.fix, upgrades: [...state.model.upgrades] },
  };
}

function setStatus(text, { error = null, progress, busy = false } = {}) {
  $("statusText").textContent = text;
  const bar = $("bar");
  bar.hidden = !busy && progress === undefined;
  bar.classList.toggle("indeterminate", busy && (progress === null || progress === undefined));
  $("barFill").style.width = progress != null ? Math.round(progress * 100) + "%" : "";
  $("errorText").hidden = !error;
  $("errorText").textContent = error || "";
}

function runFinished() { state.running = false; updateRunButton(); refreshModel(); }

$("runBtn").addEventListener("click", async () => {
  const p = currentParams();
  if (!totalStim()) { setStatus("Pick at least one neuron to stimulate first."); return; }
  state.running = true; updateRunButton();
  try {
    const r = await api("/api/runs", { json: p });
    state.job = r.job_id; state.lastParams = r.params;
    if (r.seed_note) { $("seed").value = r.params.seed; saveDraft(); }
    $("runHint").textContent = r.seed_note ? `Seed ${r.params.seed} was picked and filled in, so this run can be repeated or saved.` : "";
    showBanner(r.banner, r.is_fake);
    setStatus("Starting…", { busy: true, progress: null });
    poll();
  } catch (err) {
    setStatus("Could not start the run.", { error: err.message });
    runFinished();
  }
});

async function poll() {
  clearTimeout(state.pollTimer);
  if (!state.job) return;
  let s;
  try { s = await api(`/api/runs/${state.job}`); }
  catch (err) {
    setStatus("Lost contact with the run.", { error: err.message });
    runFinished();
    return;
  }
  const secs = `${Math.round(s.elapsed_s)} s`;
  if (s.state === "done") {
    setStatus(s.message + (s.is_fake ? "  (stand-in engine: made-up numbers)" : ""), { progress: 1 });
    runFinished();
    await showResults();
    return;
  }
  if (s.state === "failed") {
    setStatus(s.message, { error: s.error });
    showBanner(s.banner, s.is_fake);
    runFinished();
    return;
  }
  if (s.state === "building") refreshModel();
  let noProgress = "";
  if (s.progress === null && s.state === "running") {
    noProgress = " This engine does not report progress, so there is no percentage.";
    if (s.estimate_s != null) noProgress += ` Going by the previous run's speed with this model, expect roughly ${Math.max(1, Math.round(s.estimate_s))} s in total (a guess, not a measurement).`;
  }
  setStatus(`${s.message} ${secs} so far.${noProgress}`, { busy: true, progress: s.progress });
  state.pollTimer = setTimeout(poll, 500);
}

// ---------------- results --------------------------------------------------
async function showResults() {
  const id = state.job;
  const top = $("topN").value, incl = $("inclStim").checked;
  try {
    const r = await api(`/api/runs/${id}/results?top=${top}&include_stimulated=${incl}`);
    renderTable(r);
    const trials = r.n_trials;
    $("trialSelect").innerHTML = Array.from({ length: trials }, (_, i) => `<option value="${i}">${i + 1} of ${trials}</option>`).join("");
    await loadRaster(0);
    const csv = $("csvLink");
    csv.href = `/api/runs/${id}/rates.csv`; csv.hidden = false;
  } catch (err) {
    setStatus("Could not load the results.", { error: err.message });
  }
}

function groupsText(groups) {
  return (groups || []).map((g) => `${esc(g.name)} ${esc(g.rate_hz)} Hz`).join(" + ") || "none";
}

function renderTable(r) {
  const fakeTag = r.is_fake ? '<span class="fake-tag">STAND-IN ENGINE</span>' : "";
  const v = r.variant || {};
  $("resultsInfo").innerHTML =
    `Model: <b>${esc(v.label || "Published model")}</b>. ` +
    `${r.n_active_downstream.toLocaleString()} non-stimulated neurons fired at least once ` +
    `(${r.total_spikes.toLocaleString()} spikes over ${r.n_trials} trial${r.n_trials === 1 ? "" : "s"} of ${r.duration_ms} ms, ` +
    `seed ${esc(r.params.seed)}, input ${groupsText(r.stim_groups)}, snapshot ${esc(r.snapshot)}). Rates are averaged over trials.` + fakeTag +
    (r.notes && r.notes.length ? `<br>Notes: ${esc(r.notes.join("; "))}` : "");
  $("watchBox").innerHTML = r.watch.length ? `<div class="watch"><h3>Watched</h3>${r.watch.map((w) =>
    `<div><span>${esc(label(w))} <small class="hint">${esc(w.root_id)}${w.side ? " · " + esc(w.side) : ""}</small></span><span class="v">${w.rate_hz.toFixed(2)} Hz</span></div>`).join("")}</div>` : "";
  const tbody = $("rankTable").querySelector("tbody");
  tbody.innerHTML = r.top.map((n) => `
    <tr class="${n.role === "stimulated" ? "stim" : ""}">
      <td>${n.rank}</td><td>${esc(label(n))}${n.group ? ` <small class="hint">(${esc(n.group)})</small>` : ""}</td><td>${esc(n.super_class)}</td><td>${esc(n.nt)}</td>
      <td class="num">${n.rate_hz.toFixed(2)}</td><td class="num">${n.rate_sd_hz.toFixed(2)}</td>
      <td class="id">${esc(n.root_id)}</td>
      <td><button type="button" class="small" data-silence-row="${esc(n.root_id)}" title="Add to Silence, to test whether the response needs this neuron">Silence</button></td>
    </tr>`).join("");
  tbody._rows = Object.fromEntries(r.top.map((n) => [n.root_id, n]));
  $("rankTable").hidden = r.top.length === 0;
}

$("rankTable").addEventListener("click", (ev) => {
  const b = ev.target.closest("button[data-silence-row]");
  if (!b) return;
  const n = $("rankTable").querySelector("tbody")._rows[b.dataset.silenceRow];
  if (n) addTo("silence", [n]);
});
$("topN").addEventListener("change", () => state.job && showResults());
$("inclStim").addEventListener("change", () => state.job && showResults());

// ---------------- raster ---------------------------------------------------
async function loadRaster(trial) {
  const r = await api(`/api/runs/${state.job}/spikes?trial=${trial}&max_rows=150`);
  state.raster = r;
  $("trialSelect").value = String(trial);
  $("replayBtn").disabled = false;
  $("rasterInfo").textContent = `${r.rows.length} rows shown (${r.n_spikes.toLocaleString()} spikes in this trial` +
    (r.n_rows_hidden ? `; ${r.n_rows_hidden.toLocaleString()} quieter neurons not shown` : "") + ")." +
    (r.truncated ? " Too many spikes to draw them all; the list was cut short." : "") +
    (r.is_fake ? " STAND-IN ENGINE: made-up spikes." : "");
  replay();
}
$("trialSelect").addEventListener("change", (e) => state.job && loadRaster(Number(e.target.value)));
$("replayBtn").addEventListener("click", replay);

const GUTTER = 118;
function rasterGeometry() {
  const r = state.raster;
  const canvas = $("raster");
  const width = canvas.parentElement.clientWidth;
  const n = r ? r.rows.length : 0;
  const rowH = n ? Math.max(3, Math.min(14, 520 / n)) : 14;
  const labels = rowH >= 9 && width > 340;
  const left = labels ? GUTTER : 8;
  const height = Math.max(120, Math.ceil(n * rowH) + 30);
  return { canvas, width, height, rowH, labels, left, plotW: width - left - 10, top: 6 };
}

function drawRaster(upTo) {
  const r = state.raster;
  const g = rasterGeometry();
  const dpr = window.devicePixelRatio || 1;
  const { canvas } = g;
  canvas.style.height = g.height + "px";
  canvas.width = Math.round(g.width * dpr); canvas.height = Math.round(g.height * dpr);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = css("--panel"); ctx.fillRect(0, 0, g.width, g.height);
  if (!r) return;
  const accent = css("--accent"), tick = css("--tick"), muted = css("--muted"), line = css("--line");
  const T = r.duration_ms, xOf = (t) => g.left + (t / T) * g.plotW;
  ctx.font = "11px system-ui, sans-serif"; ctx.textBaseline = "middle";
  let lastRole = null;
  r.rows.forEach((row, i) => {
    const y = g.top + i * g.rowH;
    if (lastRole === "stimulated" && row.role !== "stimulated") {
      ctx.fillStyle = line; ctx.fillRect(g.left, y - 0.5, g.plotW, 1);
    }
    lastRole = row.role;
    const col = row.role === "stimulated" ? accent : tick;
    if (g.labels) {
      ctx.fillStyle = row.role === "stimulated" ? accent : muted;
      const txt = label(row);
      ctx.fillText(txt.length > 16 ? txt.slice(0, 15) + "…" : txt, 4, y + g.rowH / 2);
    }
    ctx.fillStyle = col;
    const h = Math.max(1.5, g.rowH * 0.72), w = g.plotW > 500 ? 1.3 : 1;
    for (const t of row.t_ms) {
      if (t > upTo) break;
      ctx.fillRect(xOf(t) - w / 2, y + (g.rowH - h) / 2, w, h);
    }
  });
  // time axis
  const yAxis = g.top + r.rows.length * g.rowH + 4;
  ctx.fillStyle = line; ctx.fillRect(g.left, yAxis, g.plotW, 1);
  ctx.fillStyle = muted; ctx.textBaseline = "top";
  const step = T <= 200 ? 50 : T <= 1000 ? 250 : T <= 4000 ? 1000 : 2000;
  for (let t = 0; t <= T + 1e-6; t += step) {
    const x = xOf(t);
    ctx.fillRect(x, yAxis, 1, 4);
    const s = t + (t === 0 ? " ms" : "");
    ctx.fillText(s, Math.min(Math.max(x - 8, 0), g.width - 40), yAxis + 6);
  }
  if (upTo < T) { ctx.fillStyle = accent; ctx.fillRect(xOf(upTo), g.top, 1, yAxis - g.top); }
}

function replay() {
  cancelAnimationFrame(state.replayFrame);
  const r = state.raster;
  if (!r) { drawRaster(0); return; }
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) { drawRaster(r.duration_ms); return; }
  const ms = 2500, t0 = performance.now();
  const step = (now) => {
    const f = Math.min(1, (now - t0) / ms);
    drawRaster(f * r.duration_ms);
    if (f < 1) state.replayFrame = requestAnimationFrame(step);
  };
  state.replayFrame = requestAnimationFrame(step);
}

new ResizeObserver(() => { if (state.raster) drawRaster(state.raster.duration_ms); else drawRaster(0); }).observe($("rasterWrap"));

$("raster").addEventListener("mousemove", (ev) => {
  const r = state.raster, tip = $("tip");
  if (!r) return;
  const g = rasterGeometry();
  const rect = $("raster").getBoundingClientRect();
  const y = ev.clientY - rect.top, x = ev.clientX - rect.left;
  const i = Math.floor((y - g.top) / g.rowH);
  if (i < 0 || i >= r.rows.length) { tip.hidden = true; return; }
  const row = r.rows[i];
  const t = Math.max(0, Math.min(r.duration_ms, ((x - g.left) / g.plotW) * r.duration_ms));
  tip.hidden = false;
  tip.innerHTML = `<b>${esc(label(row))}</b> · ${esc(row.role)}${row.group ? " (" + esc(row.group) + ")" : ""}<br>` +
    `${row.rate_hz.toFixed(2)} Hz average · ${row.t_ms.length} spikes this trial<br><small>${esc(row.root_id)} · ${Math.round(t)} ms</small>`;
  tip.style.left = Math.min(x + 12, rect.width - 250) + "px";
  tip.style.top = Math.min(y + 12, rect.height - 60) + "px";
});
$("raster").addEventListener("mouseleave", () => { $("tip").hidden = true; });


// ---------------- setups ---------------------------------------------------
async function loadSetupList(select) {
  try {
    const r = await api("/api/setups");
    const sel = $("setupSelect");
    sel.innerHTML = r.setups.length ? r.setups.map((s) =>
      `<option value="${esc(s.name)}">${esc(s.title)}${s.error ? " (unreadable)" : ""}</option>`).join("")
      : "<option value=\"\">No saved setups yet</option>";
    if (select) sel.value = select;
  } catch (err) { $("setupInfo").textContent = "Could not list setups: " + err.message; }
}

$("loadBtn").addEventListener("click", async () => {
  const name = $("setupSelect").value;
  if (!name) return;
  try {
    const r = await api(`/api/setups/${encodeURIComponent(name)}`);
    const s = r.setup;
    // r.params is the setup as the app runs it: a setup saved before model variants
    // existed is the published model, and its one input rate is one stimulus group.
    const p = r.params || {
      stim_groups: s.stim_groups || [{ name: "Stimulated", rate_hz: s.rate_hz, ids: s.excite || [] }],
      silence: s.silence || [], watch: s.watch || [], variant: s.variant || { fix: "none", upgrades: [] },
    };
    $("snapshot").value = s.snapshot;
    const ids = [...p.stim_groups.flatMap((g) => g.ids), ...p.silence, ...(p.watch || [])];
    const info = await api("/api/neurons/lookup", { json: { ids, snapshot: s.snapshot } });
    const byId = Object.fromEntries(info.neurons.map((n) => [n.root_id, n]));
    state.groups = p.stim_groups.map((g, i) => {
      const ng = newGroup(g.name || `Group ${i + 1}`, g.rate_hz);
      for (const id of g.ids) ng.ids.set(id, byId[id] || { root_id: id, known: false });
      return ng;
    });
    if (!state.groups.length) state.groups = [newGroup("Group 1", DEFAULT_RATE)];
    state.active = 0;
    for (const k of LISTS) {
      state.lists[k].clear();
      for (const id of p[k] || []) state.lists[k].set(id, byId[id] || { root_id: id, known: false });
    }
    $("duration").value = s.duration_ms; $("trials").value = s.n_trials; $("seed").value = s.seed;
    $("saveName").value = s.name; $("saveTitle").value = s.title; $("saveDesc").value = s.description || "";
    renderLists();
    setModel(p.variant);
    loadStatus();
    const unknown = info.neurons.filter((n) => !n.known).length;
    const modelName = (s.variant && s.variant.label) || "Published model" + (s.variant ? "" : " (saved before model choices existed)");
    $("setupInfo").textContent = `Loaded "${s.title}" (snapshot ${s.snapshot}, model: ${modelName}). ` + (s.description ? s.description + " " : "") +
      (r.params_error ? r.params_error + " " : "") +
      (r.engine_warning ? "Note: " + r.engine_warning + " " : "") +
      (unknown ? `${unknown} id(s) are not in the current neuron table (shown in red); the run will be refused until they are removed.` : "");
  } catch (err) { $("setupInfo").textContent = "Could not load it: " + err.message; }
});

$("saveBtn").addEventListener("click", async () => {
  const p = currentParams();
  const body = { ...p, name: $("saveName").value.trim(), title: $("saveTitle").value.trim(), description: $("saveDesc").value };
  if (p.seed === null) { $("saveInfo").textContent = "Fill in a seed first (or run once and the app fills one in); without it the run cannot be repeated exactly."; return; }
  try {
    const r = await api(`/api/setups?overwrite=${$("saveOverwrite").checked}`, { json: body });
    const v = r.setup.variant;
    const code = Object.entries(v.code || {}).map(([f, h]) => `${f} ${h}`).join(", ");
    $("saveInfo").textContent = `Saved as app/setups/${r.setup.name}.json (model: ${v.label}; code fingerprints: ${code}).`;
    loadSetupList(r.setup.name);
  } catch (err) { $("saveInfo").textContent = "Not saved: " + err.message; }
});

// Switching snapshot: re-check every picked id against the other brain map
// (ids that do not exist there turn red), re-check the model choice (variants
// exist for the 630 map only) and redo the search.
$("snapshot").addEventListener("change", async () => {
  saveDraft();
  loadStatus();
  refreshModel();
  const ids = [...state.groups.flatMap((g) => [...g.ids.keys()]), ...LISTS.flatMap((k) => [...state.lists[k].keys()])];
  if (ids.length) {
    try {
      const info = await api("/api/neurons/lookup", { json: { ids, snapshot: snapshot() } });
      const byId = Object.fromEntries(info.neurons.map((n) => [n.root_id, n]));
      for (const g of state.groups) for (const id of g.ids.keys()) g.ids.set(id, byId[id]);
      for (const k of LISTS) for (const id of state.lists[k].keys()) state.lists[k].set(id, byId[id]);
      renderLists();
      const unknown = info.neurons.filter((n) => !n.known).length;
      $("runHint").textContent = unknown ? `${unknown} picked id(s) do not exist in snapshot ${snapshot()} (shown in red); remove them before running.` : "";
    } catch (err) { $("runHint").textContent = "Could not re-check the picks: " + err.message; }
  }
  runSearch();
});

// ---------------- start ------------------------------------------------------
loadDraft();
renderLists();
loadStatus();
loadSetupList();
drawRaster(0);
