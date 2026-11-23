"""Stages 2-4: weather telemetry, ML scoring, Groq advisory. Stage 1 lives in corridor.py."""
import asyncio
import json
from datetime import date, timedelta

from . import ai_groq, model, weather
from .errors import ApiError

SYSTEM = (
    "You are a Travel Reliability Strategist for Indian Railways passengers. You receive the OUTPUT of a deterministic "
    "delay model plus live weather telemetry. Explain it and recommend a safe plan. Never invent or change numbers: "
    "every figure you quote must appear in the data you were given. Do not claim to know live train running status. "
    "Reply with ONLY a JSON object, no markdown."
)

PREDICT_SCHEMA = (
    'Schema: {"summary": "2-3 sentences on how reliable this journey is and why",'
    ' "buffer_recommendation": "1-2 sentences on the safe connection buffer vs the planned buffer",'
    ' "backup_strategy": ["2-4 short concrete actions: alternate departure, fallback train/flight, what to monitor"],'
    ' "watch_items": ["1-3 risks to watch, tied to the stations or weather in the data"]}'
)
COMPARE_SCHEMA = (
    'Schema: {"summary": "2-3 sentences comparing the two options",'
    ' "buffer_recommendation": "1-2 sentences on which option needs the bigger buffer",'
    ' "backup_strategy": ["2-4 short concrete actions"],'
    ' "watch_items": ["1-3 risks to watch"],'
    ' "pick": "A" or "B" or "either"}'
)


def _text_list(v, lo, hi):
    if not isinstance(v, list):
        raise ValueError("not a list")
    items = [str(x).strip()[:300] for x in v if str(x).strip()]
    if not (lo <= len(items) <= hi + 2):
        raise ValueError("bad list length")
    return items[:hi]


def validate_advisory(data, compare=False):
    if not isinstance(data, dict):
        raise ValueError("not an object")
    out = {
        "summary": str(data.get("summary", "")).strip()[:900],
        "buffer_recommendation": str(data.get("buffer_recommendation", "")).strip()[:600],
        "backup_strategy": _text_list(data.get("backup_strategy"), 1, 4),
        "watch_items": _text_list(data.get("watch_items", []), 0, 3),
    }
    if not out["summary"] or not out["buffer_recommendation"]:
        raise ValueError("missing text")
    if compare:
        pick = str(data.get("pick", "either")).strip().upper()
        out["pick"] = pick if pick in ("A", "B") else "either"
    return out


def _brief(r):
    m, c = r["metrics"], r["corridor"]
    return {
        "train": (c["train"] or {}).get("name") or r["input"]["query"],
        "route": f'{c["stations"][0]["name"]} -> {c["stations"][-1]["name"]}', "distance_km": c["distance_km"],
        "travel_date": r["input"]["travel_date"], "connection_type": r["input"]["connection_type"],
        "planned_buffer_min": m["planned_buffer_min"], "on_time_pct": m["reliability_pct"], "p50_delay_min": m["p50_min"],
        "p90_delay_min": m["p90_min"], "recommended_buffer_min": m["recommended_buffer_min"],
        "chance_of_making_connection_pct": m["p_make_planned_pct"], "verdict": m["verdict"],
        "bottleneck": c["bottleneck"]["name"], "weather_basis": r["weather"]["basis"],
        "top_factors": [f'{f["label"]}: {f["minutes"]} min' for f in r["factors"][:4]],
        "stations": [{"name": s["name"], "congestion": s["congestion"], "weather": s["weather"]} for s in c["stations"]],
    }


async def advise(results, compare=False):
    """Run the Groq strategist over one result (or two when comparing). Raises ai_groq.AIError."""
    if compare:
        user = "Option A:\n" + json.dumps(_brief(results[0])) + "\n\nOption B:\n" + json.dumps(_brief(results[1])) + "\n\n" + COMPARE_SCHEMA
    else:
        user = json.dumps(_brief(results[0])) + "\n\n" + PREDICT_SCHEMA
    data, used = await ai_groq.chat_json(SYSTEM, user, lambda d: validate_advisory(d, compare))
    data["source"], data["model"] = "groq", used
    return data


def offline_advisory(result):
    """Rule-based text used only by scripts/record_samples.py when no Groq key is available."""
    m, c = result["metrics"], result["corridor"]
    verdict = {"safe": "comfortably covers", "tight": "only just covers", "risky": "does not cover"}[m["verdict"]]
    return {
        "summary": f'Expected on-time probability is {m["reliability_pct"]}% with a median delay of {m["p50_min"]} min and a 90th-percentile delay of {m["p90_min"]} min. '
                   f'The main bottleneck is {c["bottleneck"]["name"]}.',
        "buffer_recommendation": f'The planned {m["planned_buffer_min"]} min buffer {verdict} the recommended {m["recommended_buffer_min"]} min for this connection type.',
        "backup_strategy": ["Keep one later onward option you can switch to without penalty.", "Check the live running status before leaving for the station."],
        "watch_items": [f'Congestion around {c["bottleneck"]["name"]}.'],
        "source": "rule-based", "model": None,
    }


async def telemetry(corridor, travel_date):
    pts = [(s["lat"], s["lon"]) for s in corridor["stations"]]
    return await weather.fetch_points(pts, travel_date)


async def run_one(corridor, travel_date, connection_type, buffer_min):
    wx = await telemetry(corridor, travel_date)
    return model.run(corridor, wx, travel_date, connection_type, buffer_min)


def parse_date(text):
    if not text:
        return weather.today_ist() + timedelta(days=1)
    try:
        d = date.fromisoformat(str(text)[:10])
    except ValueError:
        raise ApiError(400, "BAD_INPUT", "Travel date must look like 2026-12-27.")
    if abs((d - weather.today_ist()).days) > 800:
        raise ApiError(400, "BAD_INPUT", "Pick a travel date within the next two years.")
    return d


async def gather_models(corridors, travel_date, ctype, buffer_min):
    return await asyncio.gather(*[run_one(c, travel_date, ctype, buffer_min) for c in corridors])
