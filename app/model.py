"""Interpretable delay model: a stage-wise additive ensemble of decision stumps + a log-normal tail.

How it works (all deterministic, so every output can be re-derived from the audit box):
  1. Each factor (distance, congestion, live weather, season) is a ladder of 10 boosted stumps,
     i.e. a piecewise-constant approximation of scale * x**power.
  2. The factors add up to a raw delay S (minutes). A priority/punctuality multiplier M then
     scales it, giving the median delay  P50 = S * M.
  3. The spread sigma grows with weather stress and congestion; delay ~ LogNormal(ln P50, sigma),
     which gives P90, on-time probability and the probability of making a connection.

The stump scales are hand-calibrated planning priors, not parameters trained on live NTES data.
"""
import math
from datetime import date
from statistics import NormalDist

from . import data

ND = NormalDist()
ON_TIME_MIN = 15  # Indian Railways counts <= 15 min late as punctual


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def ladder(x, scale, power, n=10):
    """Sum of n stumps; stump k fires when x >= (k - 0.5) / n. Approximates scale * x**power."""
    x = clamp(x)
    return sum(scale * (((k / n) ** power) - (((k - 1) / n) ** power)) for k in range(1, n + 1) if x >= (k - 0.5) / n)


def point_stress(w, region):
    """0-1 operational stress from one waypoint's weather."""
    if not w:
        return 0.0
    vis = w.get("visibility_km")
    fog = 0.0 if vis is None else (1.0 if vis < 0.5 else clamp((5.0 - vis) / 5.0))
    fog *= data.FOG_SENS[region]
    rain = clamp((w.get("precip_mm") or 0) / 60.0) * data.RAIN_SENS[region]
    wind = clamp(((w.get("wind_kmh") or 0) - 30) / 40.0) * 0.5
    return clamp(0.75 * fog + 0.65 * rain + 0.25 * wind)


def seasonal_stress(region, month):
    return clamp(0.75 * data.FOG_PRIOR[region][month - 1] + 0.65 * data.RAIN_PRIOR[region][month - 1])


def _mix(values):
    return 0.45 * max(values) + 0.55 * sum(values) / len(values) if values else 0.0


def _clock(dep_min, add_min):
    total = dep_min + add_min
    return {"time": f"{int(total // 60) % 24:02d}:{int(total % 60):02d}", "day": int(total // 1440)}


def quantile(median, sigma, q):
    return median * math.exp(sigma * ND.inv_cdf(q))


def p_within(median, sigma, minutes):
    if minutes <= 0:
        return 0.0
    return ND.cdf((math.log(minutes) - math.log(median)) / sigma)


def run(corridor, wx, travel_date: date, connection_type, planned_buffer):
    """corridor: from corridor.resolve; wx: from weather.fetch_points. Returns the full result dict."""
    stations = corridor["stations"]
    month = travel_date.month
    train = corridor["train"] or {"tier": 3, "bias": 1.0, "turnaround": 0.5, "single_line": 0.0}
    dist = corridor["distance_km"]
    n = len(stations)

    live_ok = wx["source"] == "open-meteo"
    live = [point_stress(wx["points"][i], s["region"]) if live_ok else 0.0 for i, s in enumerate(stations)]
    seasonal = [seasonal_stress(s["region"], month) for s in stations]
    for i, s in enumerate(stations):
        s["stress_live"], s["stress_season"], s["weather"] = round(live[i], 3), round(seasonal[i], 3), wx["points"][i]

    interior = [s["congestion"] for s in stations[1:-1]] or [stations[0]["congestion"]]
    cong_idx = clamp(0.5 * max(interior) + 0.3 * (sum(interior) / len(interior)) + 0.2 * stations[-1]["congestion"] + 0.25 * train["single_line"])
    live_route, season_route = _mix(live), _mix(seasonal)
    w_live = (0.85 if wx["in_window"] else 0.35) if live_ok else 0.0

    l_dist, l_turn = ladder(dist / 2000.0, 11, 0.9), ladder(train["turnaround"], 6, 1.0)
    l_cong, l_wx, l_season = ladder(cong_idx, 14, 2.0), ladder(live_route, 34, 1.3), ladder(season_route, 30, 1.3)
    parts = {"distance": 2.0 + l_dist + l_turn, "congestion": l_cong, "weather": w_live * l_wx, "season": 0.6 * l_season}
    raw = sum(parts.values())
    mult = data.TIER_MULT[train["tier"]] * train["bias"]
    median = max(1.0, raw * mult)
    parts["priority"] = raw * (mult - 1.0)
    if median == 1.0 and raw * mult < 1.0:  # keep the breakdown summing to the displayed median
        parts["priority"] = 1.0 - raw

    sigma = clamp(0.50 + 0.35 * max(live_route * (1 if live_ok else 0), season_route * 0.8) + 0.15 * cong_idx + (0.05 if train["tier"] >= 3 else 0), 0.5, 1.5)
    p90 = quantile(median, sigma, 0.90)
    mean = median * math.exp(sigma ** 2 / 2)
    on_time = p_within(median, sigma, ON_TIME_MIN)

    labels = {"congestion": "Corridor Junction Congestion", "weather": "Live Weather & Visibility Impact",
              "season": "Seasonal Fog / Monsoon Vulnerability", "priority": "Train Priority Tier & Punctuality History",
              "distance": "Route Distance & Rake Turnaround"}
    factors = [{"id": k, "label": labels[k], "minutes": round(v, 1), "share_pct": round(100 * v / median, 1)}
               for k, v in sorted(parts.items(), key=lambda kv: -abs(kv[1]))]

    # buffer planning
    need, target = data.CONNECTION_TYPES[connection_type]
    recommended = int(math.ceil((need + quantile(median, sigma, target)) / 15.0) * 15)
    p_make = p_within(median, sigma, planned_buffer - need)
    verdict = "safe" if planned_buffer >= recommended else "tight" if p_make >= 0.75 else "risky"
    curve = [{"buffer": b, "p_make": round(p_within(median, sigma, b - need), 4)} for b in range(0, 421, 15)]

    # station-by-station delay build-up
    weights = [0.0]
    for i in range(1, n):
        seg = max(stations[i]["km"] - stations[i - 1]["km"], 1)
        weights.append(seg * (1 + 2 * stations[i]["congestion"] + 3 * max(live[i] * w_live, seasonal[i] * 0.6)))
    total_w = sum(weights) or 1.0
    run_w = 0.0
    for i, s in enumerate(stations):
        run_w += weights[i]
        s["cum_delay_p50"], s["cum_delay_p90"] = round(median * run_w / total_w, 1), round(p90 * run_w / total_w, 1)
        s["hotspot"] = s["congestion"] >= 0.70 or (s["congestion"] >= 0.55 and max(live[i], seasonal[i] * 0.6) >= 0.5)
    inner = range(1, n) if n > 1 else range(n)
    bn = max(inner, key=lambda i: stations[i]["congestion"] * (1 + max(live[i] * w_live, seasonal[i] * 0.6)) * (1 if i < n - 1 else 0.85))
    bottleneck = {"index": bn, "name": stations[bn]["name"], "congestion": stations[bn]["congestion"]}

    schedule = None
    if corridor["schedule"]:
        h, m = (int(x) for x in corridor["schedule"]["dep"].split(":"))
        d0, run_min = h * 60 + m, corridor["schedule"]["run_min"]
        schedule = {"dep": corridor["schedule"]["dep"], "run_min": run_min, "arr_sched": _clock(d0, run_min),
                    "arr_p50": _clock(d0, run_min + median), "arr_p90": _clock(d0, run_min + p90), "indicative": True}

    return {
        "kind": "predict",
        "input": {"query": corridor["query"], "travel_date": travel_date.isoformat(), "connection_type": connection_type, "planned_buffer_min": planned_buffer},
        "corridor": {"mode": corridor["mode"], "train": corridor["train"], "distance_km": dist, "stations": stations, "bottleneck": bottleneck, "schedule": schedule},
        "metrics": {"reliability_pct": round(on_time * 100), "p50_min": round(median), "p90_min": round(p90), "mean_min": round(mean),
                    "on_time_threshold_min": ON_TIME_MIN, "recommended_buffer_min": recommended, "planned_buffer_min": planned_buffer,
                    "min_transfer_min": need, "target_confidence_pct": round(target * 100), "p_make_planned_pct": round(p_make * 100), "verdict": verdict},
        "factors": factors,
        "buffer_curve": curve,
        "weather": {"source": wx["source"], "basis": wx["basis"], "live_weight": w_live, "forecast_window": wx["in_window"],
                    "fetched_at": wx.get("fetched_at"), "request_url": wx.get("request_url")},
        "audit": {
            "breakdown": [
                {"step": "Base delay", "input": "constant", "x": None, "formula": "2.0", "minutes": 2.0},
                {"step": "Distance", "input": "distance_km / 2000", "x": round(dist / 2000.0, 3), "formula": "ladder(x, scale 11, power 0.9)", "minutes": round(l_dist, 2)},
                {"step": "Rake turnaround", "input": "turnaround_risk", "x": train["turnaround"], "formula": "ladder(x, scale 6, power 1.0)", "minutes": round(l_turn, 2)},
                {"step": "Junction congestion", "input": "congestion_index", "x": round(cong_idx, 3), "formula": "ladder(x, scale 14, power 2.0)", "minutes": round(l_cong, 2)},
                {"step": "Live weather", "input": "live_route_stress", "x": round(live_route, 3), "formula": f"{w_live} * ladder(x, scale 34, power 1.3)", "minutes": round(w_live * l_wx, 2)},
                {"step": "Seasonal prior", "input": "seasonal_route_stress", "x": round(season_route, 3), "formula": "0.6 * ladder(x, scale 30, power 1.3)", "minutes": round(0.6 * l_season, 2)},
                {"step": "Raw delay S", "input": "sum of the above", "x": None, "formula": "sum", "minutes": round(raw, 2)},
                {"step": "Median P50", "input": "tier_multiplier * train_bias", "x": round(mult, 3), "formula": "max(1, S * multiplier)", "minutes": round(median, 2)},
            ],
            "formula": [
                "raw = distance_turnaround + congestion + w_live*weather + 0.6*season  (each a 10-stump boosted ladder)",
                "P50 = max(1, raw * tier_multiplier * train_bias)",
                "sigma = 0.50 + 0.35*max(live_stress, 0.8*season_stress) + 0.15*congestion_index (+0.05 for tier 3+)",
                "P90 = P50 * exp(1.2816 * sigma);  on-time = LogNormalCDF(15 min);  P(make) = LogNormalCDF(buffer - min_transfer)",
                "recommended buffer = min_transfer + delay quantile at the target confidence, rounded up to 15 min"],
            "inputs": {"distance_km": dist, "month": month, "congestion_index": round(cong_idx, 3), "live_route_stress": round(live_route, 3),
                       "seasonal_route_stress": round(season_route, 3), "live_weight": w_live, "raw_delay_min": round(raw, 1),
                       "tier": train["tier"], "tier_multiplier": data.TIER_MULT[train["tier"]], "train_bias": train["bias"],
                       "turnaround_risk": train["turnaround"], "single_line_share": train["single_line"], "sigma": round(sigma, 3),
                       "min_transfer_min": need, "target_confidence": target},
            "notes": ["Station coordinates and congestion/seasonal priors are bundled planning estimates.",
                      "Timetable times are indicative; check the official railway timetable before travel."],
        },
    }
