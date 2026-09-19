"""ElevenLabs: speech-to-text for voice listings, text-to-speech for reuse ideas,
and an outbound Conversational-AI phone call that alerts NGOs about surplus food."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings

API = "https://api.elevenlabs.io/v1"
IST = timezone(timedelta(hours=5, minutes=30))


class NotConfigured(RuntimeError):
    pass


def _headers() -> dict:
    if not settings.elevenlabs_api_key:
        raise NotConfigured("ELEVENLABS_API_KEY is not set")
    return {"xi-api-key": settings.elevenlabs_api_key}


async def transcribe(audio: bytes, filename: str, content_type: str) -> dict:
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{API}/speech-to-text", headers=_headers(),
                              files={"file": (filename, audio, content_type or "audio/webm")},
                              data={"model_id": settings.elevenlabs_stt_model})
        r.raise_for_status()
        body = r.json()
    return {"text": body.get("text", ""), "language": body.get("language_code")}


async def speak(text: str, voice_id: str | None = None) -> bytes:
    vid = voice_id or settings.elevenlabs_voice_id
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{API}/text-to-speech/{vid}", headers=_headers(),
                              params={"output_format": "mp3_44100_128"},
                              json={"text": text, "model_id": settings.elevenlabs_tts_model})
        r.raise_for_status()
        return r.content


async def call_ngo(to_number: str, variables: dict) -> dict:
    """Outbound call through an ElevenLabs agent with a Twilio number attached.
    The agent's prompt should use {{dish}}, {{plates}}, {{restaurant}}, {{distance_km}}, {{pickup_by}}."""
    if not (settings.elevenlabs_agent_id and settings.elevenlabs_phone_number_id):
        raise NotConfigured("ELEVENLABS_AGENT_ID / ELEVENLABS_PHONE_NUMBER_ID are not set")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{API}/convai/twilio/outbound-call", headers=_headers(), json={
            "agent_id": settings.elevenlabs_agent_id,
            "agent_phone_number_id": settings.elevenlabs_phone_number_id,
            "to_number": to_number,
            "conversation_initiation_client_data": {"dynamic_variables": {k: str(v) for k, v in variables.items()}},
        })
        r.raise_for_status()
        return r.json()


# ---------- turning "40 plates veg biryani, cooked at 9 pm" into a food draft ----------

NUM_WORDS = {"ten": 10, "fifteen": 15, "twenty": 20, "twenty five": 25, "thirty": 30, "forty": 40,
             "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "hundred": 100, "bees": 20, "tees": 30,
             "chalis": 40, "pachas": 50, "sau": 100}
FILLER = r"\b(we|have|has|there|is|are|about|around|of|left|over|leftover|surplus|extra|today|please|and|the|a|an|" \
         r"cooked|made|at|in|kept|fresh|some|approx|approximately|containers?|boxes|packed|trays?|vessels?|" \
         r"fridge|refrigerated|hot|warm|pure|only|bache|bacha|bachi|hain|hai|khana|rakha|rakhe|pada|pade|" \
         r"se|ka|ki|ke|mein|me|aur|abhi|lagbhag|taiyar)\b"


def parse_food_text(text: str, now: datetime | None = None) -> dict:
    """Best-effort parser (English / Hinglish). The seller confirms every field before publishing."""
    now = now or datetime.now(timezone.utc)
    t = text.lower()
    for w, n in sorted(NUM_WORDS.items(), key=lambda kv: -len(kv[0])):
        t = re.sub(rf"\b{w}\b", str(n), t)

    qty, unit = None, "plates"
    m = re.search(r"(\d+(?:\.\d+)?)\s*(plates?|portions?|packets?|servings?|people|log|kg|kilos?)\b", t)
    if m:
        qty = float(m.group(1))
        unit = "kg" if m.group(2).startswith(("kg", "kilo")) else "plates"

    if re.search(r"\b(non[\s-]?veg|chicken|mutton|fish|meat|prawn)\b", t):
        diet = "non_veg"
    elif re.search(r"\begg\b", t):
        diet = "egg"
    elif re.search(r"\bjain\b", t):
        diet = "jain"
    elif re.search(r"\bvegan\b", t):
        diet = "vegan"
    elif re.search(r"\b(veg|vegetarian|paneer|dal|daal|rajma|chole|sabzi|aloo|khichdi|pulao|idli|dosa|poha)\b", t):
        diet = "veg"   # inferred from the dish; the seller still confirms it
    else:
        diet = None

    storage = "refrigerated" if re.search(r"fridge|refrigerat|chilled", t) else \
        "hot_holding" if re.search(r"\b(hot|warm|chafing)\b", t) else "room_temp"
    packaging = "sealed_containers" if re.search(r"container|box|packed|parcel", t) else \
        "bulk_vessel" if re.search(r"vessel|handi|degchi|pot|patila", t) else "covered_trays"

    cooked_at = now
    tm = re.search(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)\b", t)
    if tm:
        h = int(tm.group(1)) % 12 + (12 if tm.group(3) == "pm" else 0)
        local = now.astimezone(IST).replace(hour=h, minute=int(tm.group(2) or 0), second=0, microsecond=0)
        if local > now.astimezone(IST) + timedelta(minutes=5):
            local -= timedelta(days=1)
        cooked_at = local.astimezone(timezone.utc)

    dish = t
    for pat in (m.group(0) if m else None, tm.group(0) if tm else None):
        if pat:
            dish = dish.replace(pat, " ")
    dish = re.sub(r"\b(non[\s-]?veg|veg|vegetarian|jain|vegan)\b", " ", dish)
    dish = re.sub(FILLER, " ", dish)
    dish = re.sub(r"[^a-z\s]", " ", dish)
    dish = re.sub(r"\s+", " ", dish).strip().title() or "Mixed meals"

    missing = [k for k, v in {"quantity": qty, "diet": diet}.items() if v is None]
    return {
        "category": "food_cooked", "route": "donate",
        "title": f"{int(qty) if qty and qty.is_integer() else qty or ''} {unit} {dish}".strip(),
        "quantity": qty, "unit": unit,
        "attributes": {"dish_name": dish, "diet": diet, "cooked_at": cooked_at.isoformat(),
                       "storage": storage, "packaging": packaging},
        "needs_confirmation": missing,
    }
