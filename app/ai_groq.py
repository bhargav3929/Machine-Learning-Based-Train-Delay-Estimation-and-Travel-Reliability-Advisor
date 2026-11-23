"""Every Groq call in the project goes through this module."""
import asyncio
import json
import logging
import random
import re

import httpx

from . import config, db

log = logging.getLogger("train-delay.groq")
URL = "https://api.groq.com/openai/v1/chat/completions"
PLACEHOLDERS = {"your_groq_key_here", "your-groq-key-here", "gsk_your_key_here", "changeme"}
RETRY_STATUS = {429, 500, 502, 503, 504}
TIMEOUT_S = 45
ATTEMPTS = 3

MSG_KEY = "Your Groq key was rejected. Open API Keys and paste a fresh key from console.groq.com/keys."
MSG_BUSY = "The AI service is busy right now. Wait a minute and try again."
MSG_FAIL = "The AI couldn't process this input."
MSG_NONE = "No Groq key is set up yet. Open API Keys and paste a free key from console.groq.com/keys."
MSG_NONE_HOSTED = "The AI advisor isn't available right now. Please try again later."


def none_message():
    return MSG_NONE_HOSTED if config.DEMO_MODE else MSG_NONE


class AIError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def usable_key(key):
    raw = key or ""
    k = raw.strip()
    return (bool(k) and k.lower() not in PLACEHOLDERS and not re.search(r"\s", k)
            and raw == k and k.startswith("gsk_") and len(k) > 8)


def resolve_key():
    """Return (key, source). Saved key first in local mode, then the environment."""
    if not config.DEMO_MODE:
        saved = db.kv_get("groq_api_key")
        if usable_key(saved):
            return saved, "ui"
    if usable_key(config.GROQ_API_KEY):
        return config.GROQ_API_KEY, "env"
    return None, "none"


def ai_ready():
    return resolve_key()[0] is not None


def mask(key):
    return f"gsk_...{key[-4:]}" if key else ""


def _scrub(text, key):
    text = str(text)
    if key:
        text = text.replace(key, "***")
    return re.sub(r"gsk_[A-Za-z0-9]{6,}", "gsk_***", text)[:400]


def clean_text(text):
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S | re.I)
    text = re.sub(r"```(?:json)?", "", text, flags=re.I).replace("```", "").strip()
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if start != -1 and end > start else text


def _wait_for(resp_text, attempt):
    """Backoff 1s, 2s, 4s plus jitter; honour 'try again in Xs' when X <= 20."""
    m = re.search(r"try again in ([\d.]+)s", resp_text or "", re.I)
    if m:
        try:
            x = float(m.group(1))
            if x <= 20:
                return x + random.uniform(0, 0.5)
        except ValueError:
            pass
    return (2 ** attempt) + random.uniform(0, 0.5)


async def chat_json(system, user, validate, max_tokens=1400):
    """Ask Groq for a JSON object; return (validated_dict, model_used). Raises AIError."""
    key, _ = resolve_key()
    if not key:
        raise AIError(503, "AI_NOT_CONFIGURED", none_message())
    models = [config.GROQ_MODEL]
    if config.GROQ_FALLBACK_MODEL and config.GROQ_FALLBACK_MODEL != config.GROQ_MODEL:
        models.append(config.GROQ_FALLBACK_MODEL)
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    last_busy = False
    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
        for model in models:
            messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
            parse_retried = False
            attempt = 0
            while attempt < ATTEMPTS:
                try:
                    resp = await client.post(URL, headers=headers, json={
                        "model": model, "messages": messages, "temperature": 0.2, "max_tokens": max_tokens})
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    log.warning("Groq %s network problem: %s", model, _scrub(exc, key))
                    last_busy = True
                    attempt += 1
                    if attempt < ATTEMPTS:
                        await asyncio.sleep(_wait_for("", attempt - 1))
                    continue
                if resp.status_code == 401:
                    raise AIError(502, "AI_KEY_INVALID", MSG_KEY)
                if resp.status_code in RETRY_STATUS:
                    last_busy = True
                    log.warning("Groq %s returned %s: %s", model, resp.status_code, _scrub(resp.text, key))
                    attempt += 1
                    if attempt < ATTEMPTS:
                        await asyncio.sleep(_wait_for(resp.text, attempt - 1))
                    continue
                if resp.status_code != 200:
                    log.warning("Groq %s rejected the request (%s): %s", model, resp.status_code, _scrub(resp.text, key))
                    last_busy = False
                    break  # move on to the fallback model
                try:
                    content = resp.json()["choices"][0]["message"]["content"]
                    return validate(json.loads(clean_text(content))), model
                except Exception as exc:
                    log.warning("Groq %s gave unusable output: %s", model, _scrub(exc, key))
                    last_busy = False
                    if not parse_retried:
                        parse_retried = True
                        messages = messages + [{"role": "user", "content": "Your last reply was not valid JSON for the requested schema. Reply again with ONLY the JSON object."}]
                        continue
                    break
    if last_busy:
        raise AIError(503, "AI_BUSY", MSG_BUSY)
    raise AIError(502, "AI_FAILED", MSG_FAIL)
