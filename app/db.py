"""Embedded SQLite (WAL): saved API key, run log for quotas, prediction history."""
import json
import sqlite3
import threading
import time

from .config import DB_PATH

_lock = threading.RLock()
_conn = None


def _db():
    global _conn
    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=10)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA synchronous=NORMAL")
        _conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS run_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT, client TEXT NOT NULL, ts REAL NOT NULL, day TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS run_log_client_ts ON run_log (client, ts);
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, client TEXT NOT NULL, ts REAL NOT NULL,
                kind TEXT NOT NULL, title TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS history_client ON history (client, ts);
            """
        )
        _conn.commit()
    return _conn


def init():
    with _lock:
        _db()


def kv_get(key):
    with _lock:
        row = _db().execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None


def kv_set(key, value):
    with _lock:
        _db().execute("INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
        _db().commit()


def kv_delete(key):
    with _lock:
        _db().execute("DELETE FROM kv WHERE key=?", (key,))
        _db().commit()


def purge_old(max_age_s=86400):
    cutoff = time.time() - max_age_s
    with _lock:
        _db().execute("DELETE FROM run_log WHERE ts<?", (cutoff,))
        _db().execute("DELETE FROM history WHERE ts<? AND client!='local'", (cutoff,))
        _db().commit()


def reserve_run(client, hourly_limit, ticket_runs=None, daily_cap=None):
    """Atomically check limits and record a run. Returns (slot_id, None) or (None, (code, wait_s))."""
    now = time.time()
    day = time.strftime("%Y-%m-%d", time.gmtime(now))
    with _lock:
        c = _db()
        purge_old()
        if ticket_runs is not None:
            used = c.execute("SELECT COUNT(*) n FROM run_log WHERE client=?", (client,)).fetchone()["n"]
            if used >= ticket_runs:
                return None, ("TICKET_USED_UP", 0)
        if daily_cap is not None:
            today = c.execute("SELECT COUNT(*) n FROM run_log WHERE day=? AND client!='local'", (day,)).fetchone()["n"]
            if today >= daily_cap:
                return None, ("DAILY_CAP_REACHED", 0)
        rows = c.execute("SELECT ts FROM run_log WHERE client=? AND ts>? ORDER BY ts", (client, now - 3600)).fetchall()
        if len(rows) >= hourly_limit:
            wait = int(rows[0]["ts"] + 3600 - now) + 1
            return None, ("RATE_LIMITED", max(wait, 1))
        cur = c.execute("INSERT INTO run_log(client,ts,day) VALUES(?,?,?)", (client, now, day))
        c.commit()
        return cur.lastrowid, None


def release_run(slot_id):
    with _lock:
        _db().execute("DELETE FROM run_log WHERE id=?", (slot_id,))
        _db().commit()


def hourly_used(client):
    with _lock:
        return _db().execute("SELECT COUNT(*) n FROM run_log WHERE client=? AND ts>?", (client, time.time() - 3600)).fetchone()["n"]


def ticket_used(client):
    with _lock:
        return _db().execute("SELECT COUNT(*) n FROM run_log WHERE client=?", (client,)).fetchone()["n"]


def daily_used():
    day = time.strftime("%Y-%m-%d", time.gmtime())
    with _lock:
        return _db().execute("SELECT COUNT(*) n FROM run_log WHERE day=? AND client!='local'", (day,)).fetchone()["n"]


def history_add(client, kind, title, payload):
    with _lock:
        c = _db()
        c.execute("INSERT INTO history(client,ts,kind,title,payload) VALUES(?,?,?,?,?)",
                  (client, time.time(), kind, title, json.dumps(payload)))
        c.execute("DELETE FROM history WHERE client=? AND id NOT IN (SELECT id FROM history WHERE client=? ORDER BY id DESC LIMIT 40)", (client, client))
        c.commit()


def history_list(client):
    with _lock:
        rows = _db().execute("SELECT id,ts,kind,title FROM history WHERE client=? ORDER BY id DESC LIMIT 40", (client,)).fetchall()
        return [dict(r) for r in rows]


def history_get(client, item_id):
    with _lock:
        row = _db().execute("SELECT id,ts,kind,title,payload FROM history WHERE client=? AND id=?", (client, item_id)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["payload"] = json.loads(d["payload"])
    return d


def history_clear(client):
    with _lock:
        _db().execute("DELETE FROM history WHERE client=?", (client,))
        _db().commit()
