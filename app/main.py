"""Machine Learning Based Train Delay Estimation and Travel Reliability Advisor - FastAPI app."""
import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import access, ai_groq, config, corridor, data, db, pipeline
from .errors import ApiError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("train-delay")


@asynccontextmanager
async def lifespan(_app):
    db.init()
    if config.DEMO_MODE and not config.DEMO_TICKET_SECRET:
        log.warning("Hosted mode is on but no access secret is set: every live run will be refused; samples still work.")
    yield


app = FastAPI(title=config.PROJECT_NAME, version=config.VERSION, lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


def err(status, code, message):
    return JSONResponse({"error": message, "code": code}, status_code=status)


@app.exception_handler(ApiError)
async def _api_error(_r, exc):
    return err(exc.status, exc.code, exc.message)


@app.exception_handler(ai_groq.AIError)
async def _ai_error(_r, exc):
    return err(exc.status, exc.code, exc.message)


@app.exception_handler(StarletteHTTPException)
async def _http_error(_r, exc):
    if exc.status_code == 404:
        return err(404, "NOT_FOUND", "That page or item doesn't exist.")
    if exc.status_code == 405:
        return err(405, "BAD_INPUT", "That method isn't allowed here.")
    return err(exc.status_code, "BAD_INPUT", "The request couldn't be processed.")


@app.exception_handler(RequestValidationError)
async def _validation_error(_r, _exc):
    return err(400, "BAD_INPUT", "Some of the fields in that request are invalid.")


@app.exception_handler(Exception)
async def _unhandled(_r, exc):
    log.exception("Unhandled error: %s", type(exc).__name__)
    return err(500, "AI_FAILED", "Something went wrong on the server. Please try again.")


# ---------------------------------------------------------------- standard routes
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/info")
async def api_info(request: Request):
    runs_left, demo = access.info(request)
    key, _ = ai_groq.resolve_key()
    return {
        "name": config.PROJECT_NAME, "slug": config.PROJECT_SLUG, "number": config.PROJECT_NUMBER, "version": config.VERSION,
        "mode": "demo" if config.DEMO_MODE else "local",
        "ai": {"provider": "groq", "ready": key is not None, "model": ai_groq.last_model or config.GROQ_MODEL},
        "limits": {"max_upload_mb": config.DEMO_MAX_UPLOAD_MB if config.DEMO_MODE else config.MAX_UPLOAD_MB,
                   "hourly_runs": config.HOURLY_RUNS, "runs_left": runs_left},
        "demo": demo,
        "connection_types": list(data.CONNECTION_TYPES),
    }


def _samples():
    items = []
    for path in sorted(config.SAMPLES_DIR.glob("*.json")):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        item["has_saved_result"] = (config.SAMPLES_DIR / "results" / f"{item['id']}.json").is_file()
        items.append(item)
    items.sort(key=lambda s: (s.get("order", 99), s["id"]))
    return items


@app.get("/api/samples")
async def api_samples():
    return {"samples": _samples()}


@app.get("/api/samples/{sample_id}")
async def api_sample(sample_id: str):
    item = next((s for s in _samples() if s["id"] == sample_id), None)
    if not item:
        raise ApiError(404, "NOT_FOUND", "That sample doesn't exist.")
    result = None
    if item["has_saved_result"]:
        result = json.loads((config.SAMPLES_DIR / "results" / f"{sample_id}.json").read_text(encoding="utf-8"))
    return {"id": item["id"], "title": item["title"], "input_text": item["input_text"], "result": result,
            "connection_type": item.get("connection_type"), "planned_buffer_min": item.get("planned_buffer_min"),
            "travel_date": item.get("travel_date")}


# ---------------------------------------------------------------- API keys (download version only)
def _keys_guard(request: Request):
    if config.DEMO_MODE:
        raise ApiError(404, "NOT_FOUND", "That page or item doesn't exist.")
    peer = request.client.host if request.client else ""
    if peer not in ("127.0.0.1", "::1", "localhost") or "x-forwarded-for" in request.headers or "forwarded" in request.headers:
        raise ApiError(403, "KEYS_LOCAL_ONLY", "API keys can only be changed from the computer that runs this app.")


@app.get("/api/keys")
async def keys_get(request: Request):
    if config.DEMO_MODE:
        raise ApiError(404, "NOT_FOUND", "That page or item doesn't exist.")
    key, source = ai_groq.resolve_key()
    return {"groq": {"configured": key is not None, "source": source, "masked": ai_groq.mask(key)}}


@app.post("/api/keys")
async def keys_set(request: Request):
    _keys_guard(request)
    try:
        body = await request.json()
        value = body.get("groq_api_key") if isinstance(body, dict) else None
    except Exception:
        value = None
    if not isinstance(value, str) or not ai_groq.usable_key(value.strip()):
        raise ApiError(400, "BAD_INPUT", "That doesn't look like a Groq key. It should start with gsk_ and have no spaces.")
    db.kv_set("groq_api_key", value.strip())
    return {"saved": ["groq"]}


@app.delete("/api/keys/groq")
async def keys_delete(request: Request):
    _keys_guard(request)
    db.kv_delete("groq_api_key")
    return {"removed": "groq"}


# ---------------------------------------------------------------- history
@app.get("/api/history")
async def history_list(request: Request):
    cid = access.client_id(request)
    return {"items": db.history_list(cid) if cid else []}


@app.get("/api/history/{item_id}")
async def history_item(item_id: int, request: Request):
    cid = access.client_id(request)
    item = db.history_get(cid, item_id) if cid else None
    if not item:
        raise ApiError(404, "NOT_FOUND", "That history entry doesn't exist.")
    return item


@app.delete("/api/history")
async def history_clear(request: Request):
    cid = access.client_id(request)
    if cid:
        db.history_clear(cid)
    return {"cleared": True}


# ---------------------------------------------------------------- feature routes
async def _body(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise ApiError(400, "BAD_INPUT", "Send a JSON body with the train or corridor details.")
    if not isinstance(body, dict):
        raise ApiError(400, "BAD_INPUT", "Send a JSON object with the train or corridor details.")
    return body


def _common(body):
    ctype = body.get("connection_type") or "Standard Point-to-Point Travel"
    if ctype not in data.CONNECTION_TYPES:
        raise ApiError(400, "BAD_INPUT", "Pick one of the listed connection types.")
    try:
        buffer_min = int(body.get("planned_buffer_min", 90))
    except (TypeError, ValueError):
        raise ApiError(400, "BAD_INPUT", "Planned buffer must be a number of minutes.")
    if not 0 <= buffer_min <= 1440:
        raise ApiError(400, "BAD_INPUT", "Planned buffer must be between 0 and 1440 minutes.")
    return pipeline.parse_date(body.get("travel_date")), ctype, buffer_min


def _text(body, key):
    v = body.get(key)
    if not isinstance(v, str) or not v.strip():
        raise ApiError(400, "BAD_INPUT", "Enter a train number or name, or a corridor like 'Howrah -> New Delhi'.")
    return v.strip()


def _title(result):
    t = result["corridor"]["train"]
    stops = result["corridor"]["stations"]
    return f'{t["number"]} {t["name"]}' if t else f'{stops[0]["name"]} -> {stops[-1]["name"]}'


def _event(kind, **kw):
    return (json.dumps({"event": kind, **kw}) + "\n").encode()


async def _execute(kind, corridors, params, emit):
    """Stages 2-4. Returns the final payload. Raises AIError."""
    travel_date, ctype, buffer_min = params
    compare = kind == "compare"
    await emit({"event": "stage", "stage": 2, "status": "running"})
    results = list(await pipeline.gather_models(corridors, travel_date, ctype, buffer_min))
    wx = results[0]["weather"]
    await emit({"event": "stage", "stage": 2, "status": "done", "detail": wx["basis"] if wx["source"] == "open-meteo" else "Open-Meteo unreachable - using seasonal priors"})
    await emit({"event": "stage", "stage": 3, "status": "running"})
    await asyncio.sleep(0)
    m0 = results[0]["metrics"]
    await emit({"event": "stage", "stage": 3, "status": "done", "detail": f'P50 +{m0["p50_min"]} min / P90 +{m0["p90_min"]} min / {m0["reliability_pct"]}% on time'})
    await emit({"event": "stage", "stage": 4, "status": "running"})
    advisory = await pipeline.advise(results, compare)
    await emit({"event": "stage", "stage": 4, "status": "done", "detail": f'Advisory by {advisory["model"]}'})
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if compare:
        a, b = results
        return {"kind": "compare", "generated_at": stamp, "a": a, "b": b, "advisory": advisory,
                "comparison": {"more_reliable": "A" if a["metrics"]["reliability_pct"] >= b["metrics"]["reliability_pct"] else "B",
                               "delta_reliability_pct": a["metrics"]["reliability_pct"] - b["metrics"]["reliability_pct"],
                               "delta_p50_min": a["metrics"]["p50_min"] - b["metrics"]["p50_min"],
                               "delta_p90_min": a["metrics"]["p90_min"] - b["metrics"]["p90_min"],
                               "same_corridor": a["corridor"]["stations"][0]["name"] == b["corridor"]["stations"][0]["name"]
                               and a["corridor"]["stations"][-1]["name"] == b["corridor"]["stations"][-1]["name"]}}
    result = results[0]
    result["advisory"], result["generated_at"] = advisory, stamp
    return result


async def _feature(request: Request, kind):
    body = await _body(request)
    slot = access.reserve(request)
    cid = access.client_id(request)
    try:
        params = _common(body)
        queries = [_text(body, "train_a"), _text(body, "train_b")] if kind == "compare" else [_text(body, "query")]
        corridors = [await corridor.resolve(q) for q in queries]
        if not ai_groq.ai_ready():
            raise ai_groq.AIError(503, "AI_NOT_CONFIGURED", ai_groq.none_message())
    except BaseException:
        access.release(slot)
        raise
    stream = request.query_params.get("stream") == "1"

    def finish(payload):
        title = _title(payload) if kind == "predict" else f'{_title(payload["a"])} vs {_title(payload["b"])}'
        try:
            db.history_add(cid, kind, title, payload)
        except Exception:
            log.warning("Couldn't save history")

    if not stream:
        try:
            async def noop(_e):
                return None
            payload = await _execute(kind, corridors, params, noop)
        except BaseException:
            access.release(slot)
            raise
        finish(payload)
        return payload

    async def gen():
        queue = asyncio.Queue()

        async def emit(e):
            await queue.put(e)

        async def work():
            try:
                payload = await _execute(kind, corridors, params, emit)
                finish(payload)
                await queue.put({"event": "result", "result": payload})
            except ai_groq.AIError as exc:
                access.release(slot)
                await queue.put({"event": "error", "error": exc.message, "code": exc.code})
            except BaseException as exc:
                access.release(slot)
                log.exception("Run failed: %s", type(exc).__name__)
                await queue.put({"event": "error", "error": ai_groq.MSG_FAIL, "code": "AI_FAILED"})
            await queue.put(None)

        yield _event("stage", stage=1, status="done", detail=" / ".join(f'{c["stations"][0]["name"]} -> {c["stations"][-1]["name"]}' for c in corridors))
        task = asyncio.create_task(work())
        while True:
            item = await queue.get()
            if item is None:
                break
            yield (json.dumps(item) + "\n").encode()
        await task

    return StreamingResponse(gen(), media_type="application/x-ndjson")


@app.post("/api/predict")
async def api_predict(request: Request):
    return await _feature(request, "predict")


@app.post("/api/compare-routes")
async def api_compare(request: Request):
    return await _feature(request, "compare")


# ---------------------------------------------------------------- frontend
@app.get("/")
async def index():
    return FileResponse(config.STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")
