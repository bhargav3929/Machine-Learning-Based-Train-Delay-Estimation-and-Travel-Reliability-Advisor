"""Open-Meteo geocoding and multi-waypoint weather telemetry (free, no key)."""
import time
from datetime import datetime, timedelta, timezone

import httpx

from . import config

IST = timezone(timedelta(hours=5, minutes=30))
_cache = {}
TTL_S = 600


def today_ist():
    return datetime.now(IST).date()


async def geocode(name):
    """Return dict(name, lat, lon, population) for a place in India, or None."""
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            r = await client.get(config.OPEN_METEO_GEOCODING_URL, params={"name": name, "count": 8, "language": "en", "format": "json"})
            r.raise_for_status()
            results = r.json().get("results") or []
    except Exception:
        return None
    for item in results:
        if item.get("country_code") == "IN":
            return {"name": item.get("name", name), "lat": item["latitude"], "lon": item["longitude"],
                    "population": item.get("population") or 0, "admin1": item.get("admin1")}
    return None


def _num(v, nd=1):
    return None if v is None else round(float(v), nd)


async def fetch_points(points, travel_date):
    """points: [(lat, lon)]. Returns dict(source, basis, in_window, points=[dict|None])."""
    key = (tuple((round(a, 2), round(b, 2)) for a, b in points), travel_date.isoformat())
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < TTL_S:
        return hit[1]
    days_ahead = (travel_date - today_ist()).days
    in_window = 0 <= days_ahead <= 15
    params = {
        "latitude": ",".join(f"{p[0]:.4f}" for p in points),
        "longitude": ",".join(f"{p[1]:.4f}" for p in points),
        "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,visibility,weather_code",
        "hourly": "visibility",
        "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min,wind_speed_10m_max",
        "forecast_days": 16, "timezone": "Asia/Kolkata", "wind_speed_unit": "kmh",
    }
    fetched = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = {"source": "open-meteo", "in_window": in_window, "points": [], "fetched_at": fetched, "request_url": None,
           "basis": f"forecast for {travel_date.isoformat()}" if in_window else "live current conditions (travel date is beyond the 16-day forecast window)"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(config.OPEN_METEO_FORECAST_URL, params=params)
            r.raise_for_status()
            data = r.json()
            out["request_url"] = str(r.request.url)
        if isinstance(data, dict):
            data = [data]
        iso = travel_date.isoformat()
        for d in data:
            cur, daily, hourly = d.get("current") or {}, d.get("daily") or {}, d.get("hourly") or {}
            times = daily.get("time") or []
            idx = times.index(iso) if (in_window and iso in times) else 0
            vis_m = cur.get("visibility")
            if in_window:
                vals = [v for t, v in zip(hourly.get("time") or [], hourly.get("visibility") or [])
                        if v is not None and t.startswith(iso) and int(t[11:13]) <= 10]
                if vals:
                    vis_m = min(vals)

            def day(k):
                arr = daily.get(k) or []
                return arr[idx] if idx < len(arr) else None
            tmax, tmin = day("temperature_2m_max"), day("temperature_2m_min")
            temp = (tmax + tmin) / 2 if (in_window and tmax is not None and tmin is not None) else cur.get("temperature_2m")
            wind = day("wind_speed_10m_max") if in_window else cur.get("wind_speed_10m")
            out["points"].append({
                "temp_c": _num(temp), "precip_mm": _num(day("precipitation_sum")), "wind_kmh": _num(wind),
                "visibility_km": None if vis_m is None else round(vis_m / 1000, 2), "humidity_pct": _num(cur.get("relative_humidity_2m"), 0),
                "weather_code": cur.get("weather_code"), "current_temp_c": _num(cur.get("temperature_2m")), "current_precip_mm": _num(cur.get("precipitation")), "current_wind_kmh": _num(cur.get("wind_speed_10m")),
            })
    except Exception:
        out = {"source": "unavailable", "in_window": False, "fetched_at": fetched, "request_url": None, "basis": "Open-Meteo was unreachable; seasonal priors only",
               "points": [None] * len(points)}
    if out["source"] == "open-meteo":
        _cache[key] = (time.time(), out)
    return out
