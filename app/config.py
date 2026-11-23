import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _bool(value, default=False):
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _int(value, default):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _str(name, default):
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else default


PROJECT_NAME = _str("PROJECT_NAME", "Machine Learning Based Train Delay Estimation and Travel Reliability Advisor")
PROJECT_SLUG = _str("PROJECT_SLUG", "train-delay-advisor")
PROJECT_NUMBER = _int(os.environ.get("PROJECT_NUMBER"), 7)
VERSION = "1.0.0"
HOST = _str("HOST", "127.0.0.1")
PORT = _int(os.environ.get("PORT"), 8007)
MAX_UPLOAD_MB = _int(os.environ.get("MAX_UPLOAD_MB"), 2)
DEMO_MODE = _bool(os.environ.get("DEMO_MODE"), False)
DEMO_TICKET_SECRET = os.environ.get("DEMO_TICKET_SECRET", "").strip()
DEMO_DAILY_CAP = _int(os.environ.get("DEMO_DAILY_CAP"), 200)
DEMO_MAX_UPLOAD_MB = _int(os.environ.get("DEMO_MAX_UPLOAD_MB"), 1)
TRUST_PROXY = _bool(os.environ.get("TRUST_PROXY"), False)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = _str("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_FALLBACK_MODEL = _str("GROQ_FALLBACK_MODEL", "llama-3.3-70b-versatile")

OPEN_METEO_FORECAST_URL = _str("OPEN_METEO_FORECAST_URL", "https://api.open-meteo.com/v1/forecast")
OPEN_METEO_GEOCODING_URL = _str("OPEN_METEO_GEOCODING_URL", "https://geocoding-api.open-meteo.com/v1/search")

HOURLY_RUNS = 15
DB_PATH = ROOT / "data" / "train_delay.db"
SAMPLES_DIR = ROOT / "samples"
STATIC_DIR = ROOT / "static"
