// SVG builders: station-by-station route track and connection-success curve (dark CTC palette).
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export const COLORS = { ok: "#15803D", warn: "#B45309", bad: "#B91C1C", maroon: "#8B261D", brass: "#B45309", line: "#C7B9A5", muted: "#6B5E53", ink: "#2B2118", paper: "#FAF7F2", card: "#FFFFFF", parch: "#F4EFE6" };

export function stressLevel(s, wLive) {
  const v = Math.max((s.stress_live || 0) * wLive, (s.stress_season || 0) * 0.6);
  return v < 0.2 ? "ok" : v < 0.45 ? "warn" : "bad";
}

export function visLevel(vis) {
  if (vis == null) return "muted";
  return vis >= 4 ? "ok" : vis >= 1 ? "warn" : "bad";
}

// Small weather glyph (about 18px wide) from a WMO weather code, drawn around (x, y).
export function weatherIcon(code, x, y) {
  const c = COLORS.maroon, a = COLORS.brass;
  const cloud = (col) => `<path d="M-7 4h12a4 4 0 0 0 0-8 5 5 0 0 0-9.4-1A4.5 4.5 0 0 0-7 4z" fill="none" stroke="${col}" stroke-width="1.6" stroke-linejoin="round"/>`;
  let g;
  if (code == null) g = `<circle r="5" fill="none" stroke="${COLORS.muted}" stroke-dasharray="2 2"/>`;
  else if (code === 0) g = `<circle r="4" fill="${a}"/><g stroke="${a}" stroke-width="1.5" stroke-linecap="round"><path d="M0-8v2M0 6v2M-8 0h2M6 0h2M-5.6-5.6l1.4 1.4M4.2 4.2l1.4 1.4M-5.6 5.6l1.4-1.4M4.2-4.2l1.4-1.4"/></g>`;
  else if (code <= 3) g = `<circle cx="-3" cy="-3" r="3" fill="${a}"/>${cloud(c)}`;
  else if (code === 45 || code === 48) g = `<g stroke="${c}" stroke-width="1.8" stroke-linecap="round"><path d="M-7-4h14M-9 0h14M-7 4h14"/></g>`;
  else if (code >= 95) g = `${cloud(c)}<path d="M1 3l-3 5h3l-1 4 4-6h-3z" fill="${a}"/>`;
  else if (code >= 71 && code <= 77) g = `<g stroke="${c}" stroke-width="1.6" stroke-linecap="round"><path d="M0-7v14M-6-3.5l12 7M-6 3.5l12-7"/></g>`;
  else g = `${cloud(c)}<g stroke="${c}" stroke-width="1.6" stroke-linecap="round"><path d="M-4 7l-1 3M0 7l-1 3M4 7l-1 3"/></g>`;
  return `<g transform="translate(${x} ${y})" aria-hidden="true">${g}</g>`;
}

export function timeline(r) {
  const st = r.corridor.stations, n = st.length, wl = r.weather.live_weight;
  const W = 1000, L = 74, R = 66, base = 306, top = 138;
  const x = (i) => (n === 1 ? W / 2 : L + ((W - L - R) * i) / (n - 1));
  const maxD = Math.max(st[n - 1].cum_delay_p90, 1) * 1.12;
  const y = (d) => base - ((base - top) * d) / maxD;
  const spacing = n > 1 ? (W - L - R) / (n - 1) : 200, bw = Math.min(108, spacing - 8), barW = Math.min(30, spacing / 3);
  let s = `<svg viewBox="0 0 ${W} 392" role="img" aria-label="Delay build-up along the corridor"><rect x="0" y="0" width="${W}" height="392" rx="4" fill="${COLORS.parch}"/>`;
  [0, 0.5, 1].forEach((f) => {
    const v = (maxD * f), yy = y(v);
    s += `<line x1="${L - 10}" x2="${W - R + 10}" y1="${yy}" y2="${yy}" stroke="${COLORS.line}" ${f ? 'stroke-dasharray="4 4"' : ""}/>`;
    s += `<text x="${L - 16}" y="${yy + 4}" text-anchor="end" font-size="11" class="mono-t" fill="${COLORS.muted}">+${Math.round(v)}</text>`;
  });
  s += `<text x="12" y="${top - 14}" font-size="10" fill="${COLORS.muted}">DELAY (MIN)</text>`;
  const pts = (k) => st.map((q, i) => `${x(i).toFixed(1)},${y(q[k]).toFixed(1)}`);
  // accumulated delay bars (P50) with a P90 tick above each
  st.forEach((q, i) => {
    const cx = x(i), h = Math.max(base - y(q.cum_delay_p50), 1.5);
    s += `<rect x="${cx - barW / 2}" y="${base - h}" width="${barW}" height="${h}" fill="#E9C58E" stroke="${COLORS.ink}" stroke-width="1.2"/>`;
    s += `<line x1="${cx - barW / 2 - 3}" x2="${cx + barW / 2 + 3}" y1="${y(q.cum_delay_p90)}" y2="${y(q.cum_delay_p90)}" stroke="${COLORS.bad}" stroke-width="2.5"/>`;
  });
  s += `<polyline points="${pts("cum_delay_p90").join(" ")}" fill="none" stroke="${COLORS.bad}" stroke-width="1.6" stroke-dasharray="6 4"/>`;
  s += `<polyline points="${pts("cum_delay_p50").join(" ")}" fill="none" stroke="${COLORS.maroon}" stroke-width="3"/>`;
  // railway track: twin ink rails, maroon sleepers, brass centre line
  s += `<line x1="${x(0) - 14}" x2="${x(n - 1) + 14}" y1="${base - 4}" y2="${base - 4}" stroke="${COLORS.ink}" stroke-width="2"/><line x1="${x(0) - 14}" x2="${x(n - 1) + 14}" y1="${base + 4}" y2="${base + 4}" stroke="${COLORS.ink}" stroke-width="2"/>`;
  s += `<line x1="${x(0) - 14}" x2="${x(n - 1) + 14}" y1="${base}" y2="${base}" stroke="${COLORS.maroon}" stroke-width="9" stroke-dasharray="3 9" opacity=".8"/>`;
  st.forEach((q, i) => {
    const cx = x(i), lvl = stressLevel(q, wl), isBn = r.corridor.bottleneck.index === i;
    const w = q.weather;
    const vcol = COLORS[visLevel(w && w.visibility_km)] || COLORS.muted;
    s += `<g class="station" data-i="${i}">`;
    s += `<rect x="${cx - bw / 2}" y="10" width="${bw}" height="78" rx="4" fill="${COLORS.card}" stroke="${vcol}" stroke-width="2"/>`;
    if (w) {
      s += weatherIcon(w.weather_code, cx + bw / 2 - 16, 24);
      s += `<text x="${cx - 6}" y="29" text-anchor="middle" font-size="12" font-weight="700" class="mono-t">${w.temp_c ?? "–"}°C</text>`;
      s += `<text x="${cx}" y="46" text-anchor="middle" font-size="11" class="mono-t" fill="#4a3f36">${w.precip_mm ?? 0} mm</text>`;
      s += `<text x="${cx}" y="62" text-anchor="middle" font-size="11" class="mono-t" fill="${vcol}">vis ${w.visibility_km ?? "–"} km</text>`;
      s += `<text x="${cx}" y="78" text-anchor="middle" font-size="10" fill="${COLORS.muted}">wind ${w.wind_kmh ?? "–"} km/h</text>`;
    } else {
      s += `<text x="${cx}" y="52" text-anchor="middle" font-size="11" fill="${COLORS.muted}">no telemetry</text>`;
    }
    s += `<line x1="${cx}" x2="${cx}" y1="88" y2="${base - 8}" stroke="${COLORS.line}" stroke-dasharray="2 4"/>`;
    s += `<circle cx="${cx}" cy="${y(q.cum_delay_p50)}" r="4" fill="${COLORS.maroon}"/>`;
    s += `<text x="${cx}" y="${y(q.cum_delay_p50) - 9}" text-anchor="middle" font-size="11" font-weight="700" class="mono-t" fill="${COLORS.maroon}">+${Math.round(q.cum_delay_p50)}</text>`;
    if (q.hotspot) s += `<circle cx="${cx}" cy="${base}" r="14" fill="none" stroke="${COLORS.warn}" stroke-width="2" stroke-dasharray="3 3"/>`;
    if (isBn) s += `<circle cx="${cx}" cy="${base}" r="18" fill="none" stroke="${COLORS.bad}" stroke-width="2.5"/>`;
    s += `<circle class="node" cx="${cx}" cy="${base}" r="8" fill="${COLORS[lvl]}" stroke="${COLORS.ink}" stroke-width="2.5"/>`;
    // milepost marker
    s += `<rect x="${cx - 17}" y="326" width="34" height="14" rx="2" fill="${COLORS.card}" stroke="${COLORS.ink}" stroke-width="1.2"/><text x="${cx}" y="337" text-anchor="middle" font-size="9.5" class="mono-t">${q.km} km</text>`;
    const name = q.name.length > 18 ? q.name.slice(0, 17) + "…" : q.name;
    s += `<text x="${cx}" y="357" text-anchor="middle" font-size="11" font-weight="700">${esc(name)}</text>`;
    if (isBn) s += `<text x="${cx}" y="375" text-anchor="middle" font-size="10" font-weight="700" fill="${COLORS.bad}">BOTTLENECK</text>`;
    else if (q.hotspot) s += `<text x="${cx}" y="375" text-anchor="middle" font-size="10" font-weight="700" fill="${COLORS.warn}">HOTSPOT</text>`;
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
  s += `<polyline fill="none" stroke="${COLORS.maroon}" stroke-width="3" points="${c.map((q) => `${x(q.buffer).toFixed(1)},${y(q.p_make).toFixed(1)}`).join(" ")}"/>`;
  const mark = (b, col, label, dy) => {
    const bb = Math.min(b, 420);
    return `<line x1="${x(bb)}" x2="${x(bb)}" y1="${T}" y2="${H - B}" stroke="${col}" stroke-width="2"/><text x="${x(bb) + 5}" y="${T + dy}" font-size="11" font-weight="700" fill="${col}">${label}</text>`;
  };
  s += mark(m.planned_buffer_min, COLORS.brass, `planned ${m.planned_buffer_min}`, 12);
  s += mark(m.recommended_buffer_min, COLORS.ok, `safe ${m.recommended_buffer_min}`, 28);
  return s + "</svg>";
}

// Circular on-time reliability gauge.
export function gauge(pct, level) {
  const R = 26, C = 2 * Math.PI * R, col = COLORS[level] || COLORS.maroon, off = C * (1 - Math.max(0, Math.min(100, pct)) / 100);
  return `<svg viewBox="0 0 64 64" role="img" aria-label="On-time reliability ${pct} percent"><circle cx="32" cy="32" r="${R}" fill="none" stroke="#E6DDCE" stroke-width="7"/>` +
    `<circle cx="32" cy="32" r="${R}" fill="none" stroke="${col}" stroke-width="7" stroke-linecap="round" stroke-dasharray="${C.toFixed(1)}" stroke-dashoffset="${off.toFixed(1)}" transform="rotate(-90 32 32)" /></svg>`;
}
