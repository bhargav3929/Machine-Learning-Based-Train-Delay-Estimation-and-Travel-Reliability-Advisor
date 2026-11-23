// HTML builders for results. All dynamic text goes through esc().
import { esc, timeline, bufferCurve } from "./charts.js";

const lvl = (v, ok, warn) => (v <= ok ? "ok" : v <= warn ? "warn" : "bad");
const relLvl = (p) => (p >= 75 ? "ok" : p >= 45 ? "warn" : "bad");
const VERDICT = { safe: ["ok", "Safe"], tight: ["warn", "Tight"], risky: ["bad", "Risky"] };
const dm = (n) => `+${n} min`;

function clock(c) { return c ? `${c.time}${c.day ? ` <small style="display:inline">+${c.day}d</small>` : ""}` : "–"; }

export function titleOf(r) {
  const t = r.corridor.train, s = r.corridor.stations;
  return t ? `${t.number} ${t.name}` : `${s[0].name} → ${s[s.length - 1].name}`;
}

function strip(r) {
  const m = r.metrics, v = VERDICT[m.verdict];
  return `<div class="strip">
    <div class="metric ${relLvl(m.reliability_pct)}"><div class="k">On-Time Reliability Score</div><div class="v">${m.reliability_pct}%</div><div class="s">chance of arriving within ${m.on_time_threshold_min} min of schedule</div></div>
    <div class="metric ${lvl(m.p50_min, 15, 45)}"><div class="k">Expected Median Delay (P50)</div><div class="v">${dm(m.p50_min)}</div><div class="s">half of runs are better than this</div></div>
    <div class="metric ${lvl(m.p90_min, 30, 90)}"><div class="k">90th-Percentile Tail Delay (P90)</div><div class="v">${dm(m.p90_min)}</div><div class="s">1 run in 10 is worse than this</div></div>
    <div class="metric ${v[0]}"><div class="k">Safe Connection Buffer</div><div class="v">${m.recommended_buffer_min} min</div><div class="s"><span class="chip ${v[0]}">${v[1]}</span> planned ${m.planned_buffer_min} min · ${m.p_make_planned_pct}% to make it</div></div>
  </div>`;
}

function schedule(r) {
  const s = r.corridor.schedule;
  if (!s) return "";
  return `<div class="card sched">
    <div class="clock"><small>Departs</small><b>${esc(s.dep)}</b></div>
    <div class="clock"><small>Scheduled arrival</small><b>${clock(s.arr_sched)}</b></div>
    <div class="clock"><small>Predicted arrival (P50)</small><b style="color:#0F294A">${clock(s.arr_p50)}</b></div>
    <div class="clock"><small>Worst-case arrival (P90)</small><b style="color:#DC2626">${clock(s.arr_p90)}</b></div>
    <div class="tagline" style="margin:0">Timetable times are indicative.</div></div>`;
}

function timelineCard(r, heading) {
  const bn = r.corridor.bottleneck;
  return `<div class="card"><h3>${heading || "Station-by-station delay &amp; weather propagation"}</h3>
    <div class="svgwrap">${timeline(r)}</div>
    <div class="stinfo" data-stinfo>Hover or tap a station. Bottleneck junction: <b>${esc(bn.name)}</b> (congestion ${Math.round(bn.congestion * 100)}%).</div>
    <div class="legend"><span><i style="background:#0F294A"></i>Median (P50) delay build-up</span><span><i style="background:#DC2626"></i>Worst-case (P90)</span><span>Weather badge border: fog/visibility risk</span><span>Ring: congestion hotspot</span></div>
    <div class="tagline">Weather: ${esc(r.weather.basis)}</div></div>`;
}

function factors(r) {
  const max = Math.max(...r.factors.map((f) => Math.abs(f.minutes)), 1);
  return `<div class="card"><h3>ML factor attribution</h3><div class="bars">${r.factors.map((f) => {
    const neg = f.minutes < 0;
    const col = neg ? "#059669" : f.share_pct >= 30 ? "#DC2626" : f.share_pct >= 12 ? "#D97706" : "#3b6aa8";
    return `<div class="bar"><span>${esc(f.label)}</span><div class="track"><div class="fill" style="width:${Math.max((Math.abs(f.minutes) / max) * 100, 1.5)}%;background:${col}"></div></div><span class="val">${neg ? "−" : "+"}${Math.abs(f.minutes)} min · ${f.share_pct}%</span></div>`;
  }).join("")}</div><div class="tagline">Shares add up to 100% of the median delay. A green bar means that factor shields the journey from delay.</div></div>`;
}

function advisory(r) {
  const a = r.advisory, m = r.metrics, v = VERDICT[m.verdict];
  const src = a.source === "groq" ? `Groq · ${esc(a.model)}` : "Rule-based baseline (no AI call)";
  return `<div class="cards3">
    <div class="card"><h3>Reliability summary</h3><p>${esc(a.summary)}</p>${a.watch_items && a.watch_items.length ? `<ul style="margin-top:8px">${a.watch_items.map((w) => `<li>${esc(w)}</li>`).join("")}</ul>` : ""}<div class="tagline">${src}</div></div>
    <div class="card"><h3>Safer buffer recommendation</h3><p><span class="chip ${v[0]}">${v[1]}</span> <b class="num">${m.recommended_buffer_min} min</b> recommended vs <b class="num">${m.planned_buffer_min} min</b> planned.</p><p style="margin-top:8px">${esc(a.buffer_recommendation)}</p></div>
    <div class="card"><h3>Alternative departure / backup strategy</h3><ul>${a.backup_strategy.map((b) => `<li>${esc(b)}</li>`).join("")}</ul></div>
  </div>`;
}

const WMO = (c) => (c == null ? "n/a" : c === 0 ? "clear" : c <= 3 ? "partly/overcast" : c === 45 || c === 48 ? "fog" : c < 60 ? "drizzle" : c < 70 ? "rain" : c < 80 ? "snow" : c < 90 ? "showers" : "thunderstorm");

function audit(r, open) {
  const st = r.corridor.stations, bn = r.corridor.bottleneck.index, i = r.audit.inputs, w = r.weather;
  const coord = (s) => `${s.lat.toFixed(4)}, ${s.lon.toFixed(4)}`;
  const key = [[0, "Origin"], [bn, "Mid-route bottleneck junction"], [st.length - 1, "Destination"]].filter((k, n, arr) => arr.findIndex((q) => q[0] === k[0]) === n);
  const keyRows = key.map(([idx, role]) => `<tr><td>${role}</td><td>${esc(st[idx].name)}</td><td class="num">${coord(st[idx])}</td><td>${esc(st[idx].source)}</td></tr>`).join("");
  const rows = st.map((s) => {
    const x = s.weather || {};
    return `<tr><td>${esc(s.name)}</td><td class="num">${coord(s)}</td><td class="num">${x.temp_c ?? "–"}</td><td class="num">${x.precip_mm ?? "–"}</td><td class="num">${x.wind_kmh ?? "–"}</td><td class="num">${x.visibility_km ?? "–"}</td><td>${x.weather_code ?? "–"} ${x.weather_code == null ? "" : esc(WMO(x.weather_code))}</td><td class="num">${Math.round(s.congestion * 100)}%</td><td class="num">${s.stress_live}</td><td class="num">${s.stress_season}</td></tr>`;
  }).join("");
  const bd = (r.audit.breakdown || []).map((q) => `<tr><td>${esc(q.step)}</td><td>${esc(q.input)}</td><td class="num">${q.x ?? "–"}</td><td class="mono">${esc(q.formula)}</td><td class="num">${q.minutes} min</td></tr>`).join("");
  const inputs = Object.entries(i).map(([k, v]) => `<tr><td>${esc(k)}</td><td class="num">${esc(v)}</td></tr>`).join("");
  const url = w.request_url ? `<p class="muted">Raw request (open it to check every value): <a href="${esc(w.request_url)}" target="_blank" rel="noopener" style="word-break:break-all">${esc(w.request_url)}</a></p>` : "";
  return `<details class="audit" ${open ? "open" : ""}><summary>Telemetry &amp; ML Verification Audit</summary><div class="in">
    <h4>Resolved coordinates</h4>
    <table style="min-width:520px"><thead><tr><th>Role</th><th>Station</th><th class="num">lat, lon</th><th>Coordinates from</th></tr></thead><tbody>${keyRows}</tbody></table>
    <h4>Live Open-Meteo values</h4>
    <p class="muted">Source: ${esc(w.source)} · ${esc(w.basis)} · fetched <span class="mono">${esc(w.fetched_at || "n/a")}</span> · live weight ${w.live_weight}. Temperature, rain and wind are daily values when a forecast date applies, otherwise current. Visibility is the early-morning minimum (forecast) or current.</p>
    <div class="svgwrap"><table style="min-width:860px"><thead><tr><th>Station</th><th class="num">lat, lon</th><th class="num">temperature_2m °C</th><th class="num">precipitation mm</th><th class="num">wind_speed_10m km/h</th><th class="num">visibility km</th><th>weather_code</th><th class="num">Congestion</th><th class="num">Live stress</th><th class="num">Season stress</th></tr></thead><tbody>${rows}</tbody></table></div>
    ${url}
    <h4>Delay math, step by step</h4>
    <div class="svgwrap"><table style="min-width:640px"><thead><tr><th>Step</th><th>Input</th><th class="num">x</th><th>Formula</th><th class="num">Result</th></tr></thead><tbody>${bd}</tbody></table></div>
    <h4>Model formula</h4><pre class="f">${r.audit.formula.map(esc).join("\n")}</pre>
    <h4>All deterministic inputs</h4><table style="max-width:420px"><tbody>${inputs}</tbody></table>
    <p class="muted" style="margin-top:8px">${r.audit.notes.map(esc).join(" ")}</p></div></details>`;
}

function head(r) {
  const c = r.corridor, st = c.stations;
  return `<div class="head"><h2>${esc(titleOf(r))}</h2><div class="meta mono">${esc(st[0].name)} → ${esc(st[st.length - 1].name)} · ${c.distance_km} km · ${esc(r.input.travel_date)} · ${esc(r.input.connection_type)}</div></div>`;
}

function bufferCard(r) {
  const m = r.metrics;
  const rows = [30, 60, 90, 120, 180, 240].concat([m.planned_buffer_min, m.recommended_buffer_min]).filter((v, i, a) => a.indexOf(v) === i).sort((a, b) => a - b).map((b) => {
    const p = (r.buffer_curve.find((q) => q.buffer >= b) || r.buffer_curve[r.buffer_curve.length - 1]).p_make;
    const tag = b === m.planned_buffer_min ? " (planned)" : b === m.recommended_buffer_min ? " (recommended)" : "";
    return `<tr><td class="num">${b} min${tag}</td><td class="num">${Math.round(p * 100)}%</td></tr>`;
  }).join("");
  return `<div class="card"><h3>Chance of making the connection, by buffer</h3>
    <div class="svgwrap">${bufferCurve(r)}</div>
    <p class="muted">Minimum transfer time for this connection type is ${m.min_transfer_min} min. The safe buffer targets ${m.target_confidence_pct}% confidence.</p>
    <table style="max-width:360px"><thead><tr><th class="num">Buffer</th><th class="num">Chance to make it (nearest 15 min)</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

export function rejectionHtml(r) {
  return `<div class="head"><h2>Rejected: ${esc(r.input.query)}</h2><div class="meta mono">HTTP ${r.http_status} ${esc(r.code)}</div></div>
    <div class="card" style="border-left:4px solid #DC2626"><h3>The validator refused this input</h3>
      <p><b>${esc(r.error)}</b></p>
      <p class="muted" style="margin-top:10px">No delay numbers were produced, the weather and AI were never called, and this attempt did not use any of your 15 hourly runs.</p>
      <pre class="f">POST api/predict  ->  ${r.http_status}
{"error": "${esc(r.error)}",
 "code": "${esc(r.code)}"}</pre></div>`;
}

export function predictHtml(r, view) {
  if (r.kind === "rejection") return rejectionHtml(r);
  if (view === "buffer") return head(r) + strip(r) + bufferCard(r) + advisory(r) + schedule(r) + audit(r, false);
  return head(r) + strip(r) + schedule(r) + timelineCard(r) + audit(r, false) + factors(r) + advisory(r);
}

export function compareHtml(c) {
  const { a, b, comparison: k, advisory: adv } = c;
  const col = (r, tag) => {
    const m = r.metrics, v = VERDICT[m.verdict];
    return `<div class="col card ${k.more_reliable === tag ? "winner" : ""}"><h3>Option ${tag}: ${esc(titleOf(r))}</h3>
      <div class="strip">
        <div class="metric ${relLvl(m.reliability_pct)}"><div class="k">On-time</div><div class="v">${m.reliability_pct}%</div></div>
        <div class="metric ${lvl(m.p50_min, 15, 45)}"><div class="k">P50 delay</div><div class="v">${dm(m.p50_min)}</div></div>
        <div class="metric ${lvl(m.p90_min, 30, 90)}"><div class="k">P90 delay</div><div class="v">${dm(m.p90_min)}</div></div>
        <div class="metric ${v[0]}"><div class="k">Safe buffer</div><div class="v">${m.recommended_buffer_min}m</div><div class="s"><span class="chip ${v[0]}">${v[1]}</span> vs ${m.planned_buffer_min}m planned</div></div>
      </div>${k.more_reliable === tag ? '<span class="chip ok">More reliable</span>' : ""}</div>`;
  };
  const d = (n, unit) => (n === 0 ? "equal" : `${n > 0 ? "+" : "−"}${Math.abs(n)}${unit}`);
  const pick = adv.pick && adv.pick !== "either" ? `Groq pick: Option ${adv.pick}` : "Groq pick: either option";
  return `<div class="head"><h2>Train vs. train reliability</h2><div class="meta mono">${esc(a.input.travel_date)} · ${esc(a.input.connection_type)}${k.same_corridor ? "" : " · different corridors"}</div></div>
    <div class="cmp">${col(a, "A")}${col(b, "B")}</div>
    <div class="card"><h3>Difference (A minus B)</h3><table style="max-width:520px"><tbody>
      <tr><td>On-time reliability</td><td class="num">${d(k.delta_reliability_pct, " pts")}</td></tr>
      <tr><td>Median delay</td><td class="num">${d(k.delta_p50_min, " min")}</td></tr>
      <tr><td>Tail (P90) delay</td><td class="num">${d(k.delta_p90_min, " min")}</td></tr></tbody></table></div>
    <div class="cards3">
      <div class="card"><h3>Comparison summary</h3><p>${esc(adv.summary)}</p><div class="tagline">${esc(pick)} · Groq · ${esc(adv.model)}</div></div>
      <div class="card"><h3>Safer buffer recommendation</h3><p>${esc(adv.buffer_recommendation)}</p></div>
      <div class="card"><h3>Backup strategy</h3><ul>${adv.backup_strategy.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div></div>
    ${timelineCard(a, "Option A: " + esc(titleOf(a)))}${timelineCard(b, "Option B: " + esc(titleOf(b)))}`;
}

export function stationInfo(r, i) {
  const q = r.corridor.stations[i], w = q.weather;
  const wx = w ? `${w.temp_c ?? "–"}°C, rain ${w.precip_mm ?? 0} mm, visibility ${w.visibility_km ?? "–"} km, wind ${w.wind_kmh ?? "–"} km/h` : "no live telemetry";
  return `<b>${esc(q.name)}</b> · <span class="mono">${q.km} km</span> · congestion <span class="mono">${Math.round(q.congestion * 100)}%</span> · cumulative delay <span class="mono">+${Math.round(q.cum_delay_p50)} min</span> (P90 <span class="mono">+${Math.round(q.cum_delay_p90)}</span>)<br><span class="muted">${esc(wx)}</span>`;
}
