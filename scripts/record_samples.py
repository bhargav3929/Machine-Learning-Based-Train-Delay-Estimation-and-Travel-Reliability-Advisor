"""Record real outputs for every bundled sample into samples/results/*.json.

Runs the same code path as POST /api/predict (live Open-Meteo telemetry + ML model + Groq advisory).
With a usable Groq key (saved in the app or GROQ_API_KEY in .env) the advisory comes from Groq.
Without one, pass --rule-based to record the telemetry and ML numbers with a rule-based advisory
(marked "source": "rule-based" so it is never mistaken for an AI answer).

    .venv/Scripts/python scripts/record_samples.py [--rule-based] [sample-id ...]
"""
import asyncio
import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import ai_groq, config, corridor, db, pipeline  # noqa: E402
from app.errors import ApiError  # noqa: E402


async def main(rule_based, only):
    db.init()
    out_dir = config.SAMPLES_DIR / "results"
    out_dir.mkdir(exist_ok=True)
    if not rule_based and not ai_groq.ai_ready():
        sys.exit("No usable Groq key found. Add one in the app (API Keys) or .env, or re-run with --rule-based.")
    for path in sorted(config.SAMPLES_DIR.glob("*.json")):
        s = json.loads(path.read_text(encoding="utf-8"))
        if only and s["id"] not in only:
            continue
        if s.get("expect_error"):
            try:
                await corridor.resolve(s["input_text"])
                sys.exit(f'{s["id"]} was expected to be rejected but resolved')
            except ApiError as e:
                payload = {"kind": "rejection", "input": {"query": s["input_text"]}, "http_status": e.status, "code": e.code, "error": e.message,
                           "quota_consumed": False, "delay_numbers_returned": False,
                           "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
                (out_dir / f"{s['id']}.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
                print(f'{s["id"]}: rejected {e.status} {e.code}: {e.message}')
                continue
        c = await corridor.resolve(s["input_text"])
        result = await pipeline.run_one(c, date.fromisoformat(s["travel_date"]), s["connection_type"], s["planned_buffer_min"])
        result["advisory"] = pipeline.offline_advisory(result) if rule_based else await pipeline.advise([result])
        result["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        (out_dir / f"{s['id']}.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
        m = result["metrics"]
        print(f'{s["id"]}: on-time {m["reliability_pct"]}%  P50 {m["p50_min"]}  P90 {m["p90_min"]}  buffer {m["recommended_buffer_min"]} ({m["verdict"]})  advisory={result["advisory"]["source"]}')


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    asyncio.run(main("--rule-based" in sys.argv, set(args)))
