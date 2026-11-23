// Thin fetch helpers. Every URL is relative so the app also works under a sub-path.
const TICKET_KEY = "lastsem_ticket";

export function initTicket() {
  try {
    const url = new URL(location.href);
    const t = url.searchParams.get("ticket");
    if (t) {
      sessionStorage.setItem(TICKET_KEY, t);
      url.searchParams.delete("ticket");
      history.replaceState(null, "", url.pathname + url.search + url.hash);
    }
  } catch (_) { /* storage can be blocked; the app still works for samples */ }
}

function baseHeaders(extra) {
  const h = Object.assign({ "Content-Type": "application/json" }, extra || {});
  try {
    const t = sessionStorage.getItem(TICKET_KEY);
    if (t) h["X-LastSem-Ticket"] = t;
  } catch (_) { /* ignore */ }
  return h;
}

export class ApiFail extends Error {
  constructor(message, code, status) { super(message); this.code = code; this.status = status; }
}

async function failFrom(res) {
  let body = {};
  try { body = await res.json(); } catch (_) { /* not json */ }
  return new ApiFail(body.error || "Something went wrong. Please try again.", body.code || "AI_FAILED", res.status);
}

export async function api(path, options = {}) {
  let res;
  try {
    res = await fetch(path, Object.assign({}, options, { headers: baseHeaders(options.headers) }));
  } catch (_) {
    throw new ApiFail("Can't reach the app. Check that it is still running.", "NETWORK", 0);
  }
  if (!res.ok) throw await failFrom(res);
  return res.json();
}

// POST and read newline-delimited JSON events; resolves with the final result.
export async function streamRun(path, body, onEvent) {
  let res;
  try {
    res = await fetch(path, { method: "POST", headers: baseHeaders(), body: JSON.stringify(body) });
  } catch (_) {
    throw new ApiFail("Can't reach the app. Check that it is still running.", "NETWORK", 0);
  }
  if (!res.ok) throw await failFrom(res);
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "", result = null, error = null;
  const handle = (line) => {
    if (!line.trim()) return;
    const ev = JSON.parse(line);
    if (ev.event === "result") result = ev.result;
    else if (ev.event === "error") error = new ApiFail(ev.error, ev.code, 200);
    onEvent(ev);
  };
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop();
    lines.forEach(handle);
  }
  handle(buf);
  if (error) throw error;
  if (!result) throw new ApiFail("The run ended without a result. Please try again.", "AI_FAILED", 200);
  return result;
}
