// SVG builders: station-by-station delay timeline and connection-success curve.
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const COLORS = { ok: "#059669", warn: "#D97706", bad: "#DC2626", indigo: "#0F294A", line: "#D8E0EA", muted: "#5B6B80" };

export function stressLevel(s, wLive) {
  const v = Math.max((s.stress_live || 0) * wLive, (s.stress_season || 0) * 0.6);
  return v < 0.2 ? "ok" : v < 0.45 ? "warn" : "bad";
}

export function visLevel(vis) {
  if (vis == null) return "muted";
  return vis >= 4 ? "ok" : vis >= 1 ? "warn" : "bad";
}

export function timeline(r) {
  const st = r.corridor.stations, n = st.length, wl = r.weather.live_weight;
  const W = 1000, L = 74, R = 66, base = 306, top = 138;
  const x = (i) => (n === 1 ? W / 2 : L + ((W - L - R) * i) / (n - 1));
  const maxD = Math.max(st[n - 1].cum_delay_p90, 1) * 1.12;
  const y = (d) => base - ((base - top) * d) / maxD;
  const spacing = n > 1 ? (W - L - R) / (n - 1) : 200, bw = Math.min(108, spacing - 8);
  let s = `<svg viewBox="0 0 ${W} 392" role="img" aria-label="Delay build-up along the corridor">`;
  // y grid
  [0, 0.5, 1].forEach((f) => {
    const v = (maxD * f), yy = y(v);
    s += `<line x1="${L - 10}" x2="${W - R + 10}" y1="${yy}" y2="${yy}" stroke="${COLORS.line}" ${f ? 'stroke-dasharray="3 4"' : ""}/>`;
    s += `<text x="${L - 16}" y="${yy + 4}" text-anchor="end" font-size="11" class="mono-t" fill="${COLORS.muted}">+${Math.round(v)}</text>`;
  });
  s += `<text x="12" y="${top - 14}" font-size="10" fill="${COLORS.muted}">DELAY (MIN)</text>`;
  // curves
  const pts = (k) => st.map((q, i) => `${x(i).toFixed(1)},${y(q[k]).toFixed(1)}`);
  s += `<polygon points="${x(0)},${base} ${pts("cum_delay_p50").join(" ")} ${x(n - 1)},${base}" fill="${COLORS.indigo}" opacity=".10"/>`;
  s += `<polyline points="${pts("cum_delay_p90").join(" ")}" fill="none" stroke="${COLORS.bad}" stroke-width="2" stroke-dasharray="6 4"/>`;
  s += `<polyline points="${pts("cum_delay_p50").join(" ")}" fill="none" stroke="${COLORS.indigo}" stroke-width="3"/>`;
  // baseline
  s += `<line x1="${x(0)}" x2="${x(n - 1)}" y1="${base}" y2="${base}" stroke="#9fb4d3" stroke-width="4" stroke-linecap="round"/>`;
  st.forEach((q, i) => {
    const cx = x(i), lvl = stressLevel(q, wl), isBn = r.corridor.bottleneck.index === i;
    const w = q.weather;
    // weather badge
    const vcol = COLORS[visLevel(w && w.visibility_km)] || COLORS.muted;
    s += `<g class="station" data-i="${i}">`;
    s += `<rect x="${cx - bw / 2}" y="10" width="${bw}" height="78" rx="6" fill="#fff" stroke="${vcol}" stroke-width="1.5"/>`;
    if (w) {
      s += `<text x="${cx}" y="29" text-anchor="middle" font-size="12" font-weight="600" class="mono-t">${w.temp_c ?? "–"}°C</text>`;
      s += `<text x="${cx}" y="46" text-anchor="middle" font-size="11" class="mono-t" fill="#33445c">${w.precip_mm ?? 0} mm</text>`;
      s += `<text x="${cx}" y="62" text-anchor="middle" font-size="11" class="mono-t" fill="${vcol}">vis ${w.visibility_km ?? "–"} km</text>`;
      s += `<text x="${cx}" y="78" text-anchor="middle" font-size="10" fill="${COLORS.muted}">wind ${w.wind_kmh ?? "–"} km/h</text>`;
    } else {
      s += `<text x="${cx}" y="52" text-anchor="middle" font-size="11" fill="${COLORS.muted}">no telemetry</text>`;
    }
    s += `<line x1="${cx}" x2="${cx}" y1="88" y2="${base}" stroke="${COLORS.line}" stroke-dasharray="2 4"/>`;
    // curve dot + delay label
    s += `<circle cx="${cx}" cy="${y(q.cum_delay_p50)}" r="4" fill="${COLORS.indigo}"/>`;
    s += `<text x="${cx}" y="${y(q.cum_delay_p50) - 9}" text-anchor="middle" font-size="11" font-weight="600" class="mono-t" fill="${COLORS.indigo}">+${Math.round(q.cum_delay_p50)}</text>`;
    // node
    if (q.hotspot) s += `<circle cx="${cx}" cy="${base}" r="13" fill="none" stroke="${COLORS.warn}" stroke-width="2" stroke-dasharray="3 3"/>`;
    if (isBn) s += `<circle cx="${cx}" cy="${base}" r="16" fill="none" stroke="${COLORS.bad}" stroke-width="2.5"/>`;
    s += `<circle class="node" cx="${cx}" cy="${base}" r="8" fill="${COLORS[lvl]}" stroke="#fff" stroke-width="3"/>`;
    // labels
    const name = q.name.length > 18 ? q.name.slice(0, 17) + "…" : q.name;
    s += `<text x="${cx}" y="338" text-anchor="middle" font-size="11" font-weight="600">${esc(name)}</text>`;
    s += `<text x="${cx}" y="353" text-anchor="middle" font-size="10.5" class="mono-t" fill="${COLORS.muted}">${q.km} km</text>`;
    if (isBn) s += `<text x="${cx}" y="373" text-anchor="middle" font-size="10" font-weight="700" fill="${COLORS.bad}">BOTTLENECK</text>`;
    else if (q.hotspot) s += `<text x="${cx}" y="373" text-anchor="middle" font-size="10" font-weight="700" fill="${COLORS.warn}">HOTSPOT</text>`;
    s += `<title>${esc(q.name)} – congestion ${Math.round(q.congestion * 100)}%</title></g>`;
  });
  return s + "</svg>";
}

export function bufferCurve(r) {
  const m = r.metrics, c = r.buffer_curve;
  const W = 760, H = 280, L = 52, R = 20, T = 20, B = 44;
  const x = (b) => L + ((W - L - R) * b) / 420, y = (p) => T + (H - T - B) * (1 - p);
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Chance of making the connection by buffer">`;
  [0, 0.25, 0.5, 0.75, 1].forEach((p) => {
    s += `<line x1="${L}" x2="${W - R}" y1="${y(p)}" y2="${y(p)}" stroke="${COLORS.line}"/>`;
    s += `<text x="${L - 8}" y="${y(p) + 4}" text-anchor="end" font-size="11" class="mono-t" fill="${COLORS.muted}">${Math.round(p * 100)}%</text>`;
  });
  for (let b = 0; b <= 420; b += 60) s += `<text x="${x(b)}" y="${H - 22}" text-anchor="middle" font-size="11" class="mono-t" fill="${COLORS.muted}">${b}</text>`;
  s += `<text x="${(L + W - R) / 2}" y="${H - 6}" text-anchor="middle" font-size="11" fill="${COLORS.muted}">Buffer between scheduled arrival and onward departure (min)</text>`;
  s += `<line x1="${L}" x2="${W - R}" y1="${y(m.target_confidence_pct / 100)}" y2="${y(m.target_confidence_pct / 100)}" stroke="${COLORS.ok}" stroke-dasharray="4 4"/>`;
  s += `<text x="${W - R}" y="${y(m.target_confidence_pct / 100) + 14}" text-anchor="end" font-size="10.5" fill="${COLORS.ok}">target ${m.target_confidence_pct}%</text>`;
  s += `<polyline fill="none" stroke="${COLORS.indigo}" stroke-width="3" points="${c.map((q) => `${x(q.buffer).toFixed(1)},${y(q.p_make).toFixed(1)}`).join(" ")}"/>`;
  const mark = (b, col, label, dy) => {
    const bb = Math.min(b, 420);
    return `<line x1="${x(bb)}" x2="${x(bb)}" y1="${T}" y2="${H - B}" stroke="${col}" stroke-width="2"/><text x="${x(bb) + 5}" y="${T + dy}" font-size="11" font-weight="700" fill="${col}">${label}</text>`;
  };
  s += mark(m.planned_buffer_min, COLORS.indigo, `planned ${m.planned_buffer_min}`, 12);
  s += mark(m.recommended_buffer_min, COLORS.ok, `safe ${m.recommended_buffer_min}`, 28);
  return s + "</svg>";
}
