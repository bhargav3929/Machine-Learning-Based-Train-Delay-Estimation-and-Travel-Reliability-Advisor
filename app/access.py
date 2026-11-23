"""Who may run live analyses: a local hourly quota, or signed access tokens in the hosted mode."""
import base64
import hashlib
import hmac
import json
import time

from . import config, db
from .errors import ApiError

HEADER = "X-LastSem-Ticket"
LOCAL_CLIENT = "local"

MESSAGES = {
    "TICKET_REQUIRED": (401, "Sign in on lastsem.com to try your own input."),
    "TICKET_INVALID": (401, "This access link isn't valid. Open the demo again from lastsem.com."),
    "TICKET_EXPIRED": (401, "This access link has expired. Open the demo again from lastsem.com."),
    "TICKET_USED_UP": (429, "You've used all the live runs on this access link."),
    "DAILY_CAP_REACHED": (429, "The demo has reached its daily limit. Please try again tomorrow."),
}


def _b64d(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def verify_token(token, secret, slug):
    """Return (payload, None) when valid, else (None, error_code)."""
    if not token:
        return None, "TICKET_REQUIRED"
    if not secret:
        return None, "TICKET_INVALID"
    try:
        body, sig = token.split(".")
        payload = json.loads(_b64d(body))
        expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
        if payload.get("v") != 1 or not hmac.compare_digest(expected, _b64d(sig)):
            return None, "TICKET_INVALID"
    except Exception:
        return None, "TICKET_INVALID"
    if payload.get("slug") not in (slug, "*"):
        return None, "TICKET_INVALID"
    if int(payload.get("exp", 0)) < time.time():
        return None, "TICKET_EXPIRED"
    return payload, None


def _identify(request):
    """Return (client_id, payload, error_code)."""
    if not config.DEMO_MODE:
        return LOCAL_CLIENT, None, None
    payload, err = verify_token(request.headers.get(HEADER), config.DEMO_TICKET_SECRET, config.PROJECT_SLUG)
    if err:
        return None, None, err
    return str(payload.get("tid")), payload, None


def client_id(request):
    cid, _, err = _identify(request)
    return None if err else cid


def info(request):
    """Numbers for /api/info: (runs_left, demo_block_or_None)."""
    cid, payload, err = _identify(request)
    if not config.DEMO_MODE:
        return max(config.HOURLY_RUNS - db.hourly_used(cid), 0), None
    capped = db.daily_used() >= config.DEMO_DAILY_CAP
    if err:
        return 0, {"ticket_valid": False, "runs_left": 0, "daily_cap_reached": capped}
    left = max(min(int(payload.get("runs", 0)) - db.ticket_used(cid), config.HOURLY_RUNS - db.hourly_used(cid)), 0)
    return left, {"ticket_valid": True, "runs_left": left, "daily_cap_reached": capped}


def reserve(request):
    """Check access and take one run slot. Raises ApiError. Pair with release() on failure."""
    cid, payload, err = _identify(request)
    if err:
        status, msg = MESSAGES[err]
        raise ApiError(status, err, msg)
    ticket_runs = int(payload.get("runs", 0)) if payload else None
    daily = config.DEMO_DAILY_CAP if config.DEMO_MODE else None
    slot, problem = db.reserve_run(cid, config.HOURLY_RUNS, ticket_runs, daily)
    if problem:
        code, wait = problem
        if code == "RATE_LIMITED":
            mins = max(1, round(wait / 60))
            raise ApiError(429, "RATE_LIMITED", f"You've used all {config.HOURLY_RUNS} runs for this hour. A slot frees up in about {mins} min.")
        status, msg = MESSAGES[code]
        raise ApiError(status, code, msg)
    return slot


def release(slot):
    if slot is not None:
        db.release_run(slot)
