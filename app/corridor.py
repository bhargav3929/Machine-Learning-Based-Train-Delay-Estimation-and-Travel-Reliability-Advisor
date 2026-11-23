"""Stage 1: turn 'train number / name' or 'Origin -> Destination' into a route with coordinates."""
import math
import re

from . import data, weather
from .errors import ApiError

STOP = {"jn", "junction", "railway", "station", "rly", "stn", "terminus"}
ARROW = re.compile(r"\s*(?:->|=>|→|–>|\bto\b)\s*", re.I)


def _norm(text):
    words = re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()).split()
    return " ".join(w for w in words if w not in STOP)


_ALIAS = {}
for _code, _s in data.STATIONS.items():
    for _a in [_s[0], _code] + list(_s[5]):
        _ALIAS.setdefault(_norm(_a), _code)


def km_between(a, b):
    r = 6371.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _station(code, km):
    s = data.STATIONS[code]
    return {"code": code, "name": s[0], "lat": s[1], "lon": s[2], "region": s[3], "congestion": s[4], "km": km, "source": "bundled"}


def find_train(query):
    q = _norm(query)
    m = re.search(r"\b(\d{5})\b", query or "")
    if m:
        return m.group(1), m.group(1) in data.TRAINS
    for number, t in data.TRAINS.items():
        if any(k in q for k in t["keys"]) or _norm(t["name"]) in q:
            return number, True
    return None, False


async def _lookup(name):
    code = _ALIAS.get(_norm(name))
    if code:
        return _station(code, 0)
    g = await weather.geocode(re.sub(r"\b(jn|junction|railway station|station)\b", "", name, flags=re.I).strip() or name)
    if not g:
        raise ApiError(400, "BAD_INPUT", f"Couldn't find a station called '{name.strip()}'. Check the spelling or try the nearest major city.")
    pop = g["population"]
    return {"code": None, "name": g["name"], "lat": g["lat"], "lon": g["lon"], "region": data.region_for(g["lat"], g["lon"]),
            "congestion": 0.70 if pop > 2_000_000 else 0.55 if pop > 500_000 else 0.40, "km": 0, "source": "open-meteo-geocoding"}


def _junctions_between(a, b, max_n=4):
    """Bundled stations that sit within ~60 km of the straight line origin -> destination."""
    lat0 = (a["lat"] + b["lat"]) / 2
    kx, ky = 111.32 * math.cos(math.radians(lat0)), 110.57
    ax, ay, bx, by = a["lon"] * kx, a["lat"] * ky, b["lon"] * kx, b["lat"] * ky
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy or 1.0
    found = []
    for code, s in data.STATIONS.items():
        px, py = s[2] * kx, s[1] * ky
        t = ((px - ax) * dx + (py - ay) * dy) / length2
        if 0.08 < t < 0.92:
            cx, cy = ax + t * dx, ay + t * dy
            off = math.hypot(px - cx, py - cy)
            if off <= 60 and code not in (a["code"], b["code"]):
                found.append((t, code))
    found.sort()
    if len(found) > max_n:  # keep the busiest ones, preserving route order
        keep = sorted(sorted(found, key=lambda x: -data.STATIONS[x[1]][4])[:max_n])
        found = keep
    return found


async def resolve(query):
    """Return a corridor dict. Raises ApiError(400, BAD_INPUT) when nothing can be recognised."""
    query = (query or "").strip()
    if not query:
        raise ApiError(400, "BAD_INPUT", "Enter a train number or name, or a corridor like 'Howrah -> New Delhi'.")
    if len(query) > 200:
        raise ApiError(400, "BAD_INPUT", "That corridor text is too long. Keep it under 200 characters.")
    number, known = find_train(query)
    if known:
        t = data.TRAINS[number]
        stations = [_station(code, km) for code, km in t["route"]]
        return {"mode": "train", "query": query, "distance_km": t["route"][-1][1], "stations": stations,
                "train": {"number": number, "name": t["name"], "tier": t["tier"], "tier_label": data.TIER_LABELS[t["tier"]],
                          "bias": t["bias"], "turnaround": t["turnaround"], "single_line": t["single_line"]},
                "schedule": {"dep": t["dep"], "run_min": t["run_min"]} if t.get("dep") else None}
    parts = [p for p in ARROW.split(re.sub(r"\(.*?\)", " ", query)) if p.strip()]
    parts = [re.sub(r"^\s*\d{5}\s+", "", p).strip() for p in parts]
    if len(parts) != 2:
        if number:
            raise ApiError(400, "BAD_INPUT", f"Couldn't recognize that train number or station corridor ({number} isn't in the bundled timetable). Try a listed train, or enter a corridor like 'Origin -> Destination'.")
        raise ApiError(400, "BAD_INPUT", "Couldn't recognize that train number or station corridor. Try a train number like 12301, or a corridor like 'Origin -> Destination'.")
    origin, dest = await _lookup(parts[0]), await _lookup(parts[1])
    straight = km_between((origin["lat"], origin["lon"]), (dest["lat"], dest["lon"]))
    if straight < 30:
        raise ApiError(400, "BAD_INPUT", "Origin and destination are almost the same place. Pick two stations that are further apart.")
    total = round(straight * 1.25)
    mids = [_station(code, round(total * t)) for t, code in _junctions_between(origin, dest)]
    origin["km"], dest["km"] = 0, total
    stations = [origin] + mids + [dest]
    return {"mode": "custom", "query": query, "distance_km": total, "stations": stations, "train": None, "schedule": None}
