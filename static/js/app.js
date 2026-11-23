import { api, initTicket, streamRun } from "./api.js";
import { esc } from "./charts.js";
import { compareHtml, predictHtml, stationInfo, titleOf } from "./render.js";

const $ = (id) => document.getElementById(id);
const state = { view: "predict", info: null, results: { predict: null, compare: null }, banner: "" };

function today(offset = 1) {
  const d = new Date(Date.now() + offset * 86400000);
  return d.toISOString().slice(0, 10);
}

function setNotice(el, html, kind) {
  el.hidden = !html;
  el.className = "notice" + (kind === "info" ? " info" : "");
  el.innerHTML = html || "";
}

/* ------------------------------------------------------------- info + pill */
async function loadInfo() {
  try {
    state.info = await api("api/info");
  } catch (e) {
    setNotice($("notice"), esc(e.message));
    return;
  }
  const i = state.info, left = i.limits.runs_left;
  $("runsLeft").textContent = left;
  $("runsPill").className = "pill" + (left === 0 ? " none" : left <= 3 ? " low" : "");
  $("keysBtn").hidden = i.mode === "demo";
  if (!$("ctype").options.length) {
    $("ctype").innerHTML = i.connection_types.map((c) => `<option>${esc(c)}</option>`).join("");
  }
  if (i.mode === "demo" && i.demo && !i.demo.ticket_valid) {
    setNotice($("notice"), "Samples work instantly. Sign in on lastsem.com to try your own input.", "info");
  }
}

/* ------------------------------------------------------------- tabs */
function setView(view) {
  state.view = view;
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  $("fieldB").hidden = view !== "compare";
  $("queryB").required = view === "compare";
  $("labelA").textContent = view === "compare" ? "Option A: train number / name or corridor" : "Train number / name or route corridor";
  $("runBtn").textContent = view === "compare" ? "Run Train Duel" : view === "buffer" ? "Compute Buffer Matrix" : "Analyze Corridor Reliability";
  renderCanvas();
}

function renderCanvas() {
  const kind = state.view === "compare" ? "compare" : "predict";
  const r = state.results[kind];
  $("empty").hidden = !!r;
  $("result").hidden = !r;
  if (!r) return;
  const banner = state.banner ? `<div class="banner">${state.banner}</div>` : "";
  $("result").innerHTML = banner + (kind === "compare" ? compareHtml(r) : predictHtml(r, state.view));
  bindStations(r, kind);
}

function bindStations(r, kind) {
  const boxes = $("result").querySelectorAll("[data-stinfo]");
  const results = kind === "compare" ? [r.a, r.b] : [r];
  $("result").querySelectorAll(".svgwrap svg").forEach((svg, idx) => {
    const owner = results[idx] || results[0];
    const box = boxes[idx];
    if (!box || !owner || !owner.corridor) return;
    svg.querySelectorAll(".station").forEach((g) => {
      const show = () => { box.innerHTML = stationInfo(owner, Number(g.dataset.i)); };
      g.addEventListener("mouseenter", show);
      g.addEventListener("click", show);
    });
  });
}

/* ------------------------------------------------------------- tracker */
function resetTracker() {
  document.querySelectorAll("#tracker li").forEach((li) => { li.className = ""; });
}
function setStage(n, status, detail) {
  const li = document.querySelector(`#tracker li[data-stage="${n}"]`);
  if (!li) return;
  li.className = status;
  if (detail) li.querySelector("small").textContent = detail;
}

/* ------------------------------------------------------------- run */
async function run(ev) {
  ev.preventDefault();
  const compare = state.view === "compare";
  const body = { travel_date: $("date").value, connection_type: $("ctype").value, planned_buffer_min: Number($("buffer").value) };
  if (compare) { body.train_a = $("query").value; body.train_b = $("queryB").value; } else { body.query = $("query").value; }
  setNotice($("notice"), "");
  resetTracker();
  setStage(1, "running", "Resolving stations…");
  $("runBtn").disabled = true;
  try {
    const result = await streamRun(compare ? "api/compare-routes?stream=1" : "api/predict?stream=1", body, (e) => {
      if (e.event === "stage") setStage(e.stage, e.status, e.detail);
      if (e.event === "stage" && e.stage === 1 && e.status === "done") setStage(2, "running");
    });
    state.results[compare ? "compare" : "predict"] = result;
    state.banner = "";
    document.querySelectorAll(".sample").forEach((s) => s.classList.remove("active"));
    renderCanvas();
  } catch (e) {
    const failed = document.querySelector("#tracker li.running");
    if (failed) failed.className = "error";
    else setStage(1, "error", "Couldn't resolve this corridor");
    let html = esc(e.message);
    if (e.code === "AI_NOT_CONFIGURED" || e.code === "AI_KEY_INVALID") {
      if (state.info && state.info.mode !== "demo") html += ' <button type="button" class="btn sm" id="openKeys">Open API Keys</button>';
    }
    setNotice($("notice"), html);
    const k = $("openKeys");
    if (k) k.addEventListener("click", openKeys);
  } finally {
    $("runBtn").disabled = false;
    loadInfo();
  }
}

/* ------------------------------------------------------------- samples */
async function loadSamples() {
  try {
    const { samples } = await api("api/samples");
    const label = (s) => (s.id.startsWith("invalid") ? s.input_text : s.title).replace(/\s*\(.*$/, "");
    $("samples").innerHTML = samples.map((s) => `<button type="button" class="sample ${s.id.startsWith("invalid") ? "reject" : /control/i.test(s.input_text) ? "control" : ""}" data-id="${esc(s.id)}" title="${esc(s.blurb || "")}">
      <b>${esc(label(s))}</b><span class="tag">${s.planned_buffer_min} min${s.has_saved_result ? " · saved" : ""}</span></button>`).join("");
    $("samples").querySelectorAll(".sample").forEach((b) => b.addEventListener("click", () => openSample(b.dataset.id, b)));
  } catch (e) {
    $("samples").textContent = e.message;
  }
}

async function openSample(id, btn) {
  try {
    const s = await api(`api/samples/${encodeURIComponent(id)}`);
    $("query").value = s.input_text;
    if (s.travel_date) $("date").value = s.travel_date;
    if (s.connection_type) $("ctype").value = s.connection_type;
    if (s.planned_buffer_min != null) $("buffer").value = s.planned_buffer_min;
    document.querySelectorAll(".sample").forEach((x) => x.classList.toggle("active", x === btn));
    setNotice($("notice"), "");
    resetTracker();
    if (s.result) {
      if (state.view === "compare") setView("predict");
      state.results.predict = s.result;
      const when = (s.result.generated_at || "").replace("T", " ").replace("Z", " UTC");
      state.banner = s.result.kind === "rejection" ? `Saved rejection recorded ${esc(when)}. Press <b>Analyze Corridor Reliability</b> to watch the validator reject it again.` : `Saved result recorded ${esc(when)}. Press <b>Analyze Corridor Reliability</b> for fresh telemetry.`;
      renderCanvas();
    }
  } catch (e) {
    setNotice($("notice"), esc(e.message));
  }
}

/* ------------------------------------------------------------- history */
async function openHistory() {
  $("drawer").classList.add("open");
  $("drawer").setAttribute("aria-hidden", "false");
  const list = $("historyList");
  try {
    const { items } = await api("api/history");
    list.innerHTML = items.length ? items.map((h) => `<li><button data-id="${h.id}">${esc(h.title)}<small>${new Date(h.ts * 1000).toLocaleString()} · ${esc(h.kind)}</small></button></li>`).join("") : '<li class="muted" style="padding:10px">No runs yet.</li>';
    list.querySelectorAll("button").forEach((b) => b.addEventListener("click", async () => {
      const item = await api(`api/history/${b.dataset.id}`);
      const kind = item.kind === "compare" ? "compare" : "predict";
      state.results[kind] = item.payload;
      state.banner = `Showing a run from history (${esc(new Date(item.ts * 1000).toLocaleString())}).`;
      if (kind === "compare") setView("compare"); else if (state.view === "compare") setView("predict"); else renderCanvas();
      closeHistory();
    }));
  } catch (e) {
    list.innerHTML = `<li class="muted" style="padding:10px">${esc(e.message)}</li>`;
  }
}
function closeHistory() { $("drawer").classList.remove("open"); $("drawer").setAttribute("aria-hidden", "true"); }

/* ------------------------------------------------------------- keys */
async function refreshKeys() {
  const note = $("keyNotice");
  setNotice(note, "");
  try {
    const { groq } = await api("api/keys");
    $("keyStatus").textContent = groq.configured ? `Key active (${groq.source === "ui" ? "saved in app" : "from .env"}): ${groq.masked}` : "No key yet.";
  } catch (e) {
    setNotice(note, esc(e.message));
  }
}
function openKeys() { $("keyInput").value = ""; refreshKeys(); $("keysDialog").showModal(); }
async function saveKey() {
  try {
    await api("api/keys", { method: "POST", body: JSON.stringify({ groq_api_key: $("keyInput").value.trim() }) });
    $("keyInput").value = "";
    await refreshKeys(); loadInfo();
  } catch (e) { setNotice($("keyNotice"), esc(e.message)); }
}
async function removeKey() {
  try { await api("api/keys/groq", { method: "DELETE" }); await refreshKeys(); loadInfo(); }
  catch (e) { setNotice($("keyNotice"), esc(e.message)); }
}

/* ------------------------------------------------------------- boot */
function boot() {
  initTicket();
  $("date").value = today(1);
  document.querySelectorAll("#tabs button").forEach((b) => b.addEventListener("click", () => setView(b.dataset.view)));
  document.querySelectorAll("[data-fill]").forEach((b) => b.addEventListener("click", () => {
    const target = state.view === "compare" && $("query").value && !$("queryB").value ? $("queryB") : $("query");
    target.value = b.dataset.fill;
  }));
  $("form").addEventListener("submit", run);
  $("keysBtn").addEventListener("click", openKeys);
  $("keySave").addEventListener("click", saveKey);
  $("keyRemove").addEventListener("click", removeKey);
  $("historyBtn").addEventListener("click", openHistory);
  $("historyClose").addEventListener("click", closeHistory);
  $("historyClear").addEventListener("click", async () => { await api("api/history", { method: "DELETE" }); openHistory(); });
  loadInfo().then(loadSamples);
}
boot();
export { titleOf };
