"""Vision AI behind one interface: Groq (free tier), Gemini, Ollama (local) or a mock.

The model only *identifies* (category, material, condition, colour, defects, reuse ideas).
Prices come from the rule-based valuation, never from the model.
If the configured provider fails, we fall back to the mock so a live demo never dead-ends.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import re
from typing import Literal

import httpx
from PIL import Image
from pydantic import BaseModel, Field, ValidationError

from app.catalog import CATEGORIES, CONDITIONS
from app.config import settings

log = logging.getLogger(__name__)


class ReuseIdea(BaseModel):
    title: str
    difficulty: Literal["easy", "medium", "hard"] = "easy"
    steps: list[str] = []


class VisionResult(BaseModel):
    category: str | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    material: str | None = None
    description: str = ""
    condition: str | None = None
    visible_color_name: str | None = None
    color_matches_manufacturer: Literal["yes", "no", "unsure"] | None = None
    defects_seen: list[str] = []
    suggested_attributes: dict = {}
    reuse_ideas: list[ReuseIdea] = []
    safety_flags: list[str] = []
    provider: str = "mock"
    warnings: list[str] = []


def _catalogue_brief() -> str:
    lines = []
    for spec in CATEGORIES.values():
        attrs = ", ".join(
            f"{a.key}({'|'.join(a.options)})" if a.options else f"{a.key}:{a.type}" for a in spec.attributes
        )
        lines.append(f"- {spec.key}: {spec.label}. attributes: {attrs}")
    return "\n".join(lines)


def build_prompt(hint_category: str | None, manufacturer_color: str | None, notes: str | None) -> str:
    return f"""You are the intake inspector for a waste-reuse marketplace in India.
Look at the photo(s) of an item someone wants to reuse, resell, recycle or donate.

Categories and their attribute keys (use "other" for anything that fits none of them, e.g. a water bottle):
{_catalogue_brief()}

Return ONLY a JSON object with these keys:
category (one of the keys above, or null), confidence (0-1), material, description (one sentence),
condition (one of {list(CONDITIONS)}), visible_color_name,
color_matches_manufacturer ("yes" | "no" | "unsure" | null) comparing what you see with the stated manufacturer colour,
defects_seen (list of short strings), suggested_attributes (object using ONLY the attribute keys of the chosen category,
enum values must be one of the listed options; omit anything you can't see),
reuse_ideas (3 items: {{"title","difficulty":"easy|medium|hard","steps":[3-5 short steps]}}),
safety_flags (e.g. "food looks spoiled", "exposed wiring", "asbestos-like sheet"; empty if none).

Seller's hint for category: {hint_category or "none"}
Manufacturer colour stated by seller: {manufacturer_color or "not given"} (lighting can shift colours; answer "unsure" if lighting is poor)
Seller notes: {notes or "none"}"""


def _prep(data: bytes, max_side: int = 1024) -> str:
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def _extract_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0) if m else text)


def clean(raw: dict, provider: str) -> VisionResult:
    raw = dict(raw or {})
    cat = raw.get("category")
    spec = CATEGORIES.get(cat) if isinstance(cat, str) else None
    raw["category"] = spec.key if spec else None
    if raw.get("condition") not in CONDITIONS:
        raw["condition"] = None
    attrs = {}
    if spec:
        for k, v in (raw.get("suggested_attributes") or {}).items():
            a = spec.attr(k)
            if not a or v in (None, ""):
                continue
            if a.options:
                v = str(v).strip().lower().replace(" ", "_").replace("-", "_")
                if v not in a.options:
                    continue
            attrs[k] = v
    raw["suggested_attributes"] = attrs
    if raw.get("color_matches_manufacturer") not in ("yes", "no", "unsure"):
        raw["color_matches_manufacturer"] = None
    ideas = []
    for idea in raw.get("reuse_ideas") or []:
        if isinstance(idea, str):
            idea = {"title": idea}
        if isinstance(idea, dict) and idea.get("title"):
            if idea.get("difficulty") not in ("easy", "medium", "hard"):
                idea["difficulty"] = "easy"
            ideas.append(idea)
    raw["reuse_ideas"] = ideas[:5]
    try:
        raw["confidence"] = min(1.0, max(0.0, float(raw.get("confidence") or 0)))
    except (TypeError, ValueError):
        raw["confidence"] = 0.0
    raw["provider"] = provider
    return VisionResult.model_validate(raw)


async def _gemini(prompt: str, images: list[str]) -> dict:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    parts = [{"text": prompt}] + [{"inline_data": {"mime_type": "image/jpeg", "data": b}} for b in images]
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}}
    async with httpx.AsyncClient(timeout=settings.vision_timeout_s) as client:
        r = await client.post(url, json=body, headers={"x-goog-api-key": settings.gemini_api_key})
        r.raise_for_status()
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return _extract_json(text)


async def _groq(prompt: str, images: list[str]) -> dict:
    """Groq's OpenAI-compatible API. Qwen vision models accept up to 3 images; thinking is switched off."""
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not set")
    content = [{"type": "text", "text": prompt}] + [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}"}} for b in images[:3]]
    body = {"model": settings.groq_vision_model, "temperature": 0.2,
            "messages": [{"role": "user", "content": content}],
            "response_format": {"type": "json_object"},
            "reasoning_effort": "none", "reasoning_format": "hidden"}
    async with httpx.AsyncClient(timeout=settings.vision_timeout_s) as client:
        r = await client.post("https://api.groq.com/openai/v1/chat/completions", json=body,
                              headers={"Authorization": f"Bearer {settings.groq_api_key}"})
        r.raise_for_status()
        return _extract_json(r.json()["choices"][0]["message"]["content"])


async def _ollama(prompt: str, images: list[str]) -> dict:
    body = {"model": settings.ollama_model, "stream": False, "format": "json",
            "options": {"temperature": 0.2},
            "messages": [{"role": "user", "content": prompt, "images": images}]}
    async with httpx.AsyncClient(timeout=settings.vision_timeout_s) as client:
        r = await client.post(f"{settings.ollama_url}/api/chat", json=body)
        r.raise_for_status()
        return _extract_json(r.json()["message"]["content"])


def mock(hint_category: str | None, filenames: list[str] | None = None) -> dict:
    """Deterministic stand-in: uses the hint, then filename keywords."""
    cat = hint_category if hint_category in CATEGORIES else None
    if not cat:
        blob = " ".join(filenames or []).lower()
        for key, words in {"tiles": ("tile",), "food_cooked": ("food", "biryani", "rice", "meal"),
                           "clothing": ("shirt", "hoodie", "cloth", "jeans"), "electronics": ("laptop", "phone", "monitor"),
                           "furniture": ("chair", "table", "desk"), "wood": ("wood", "ply"), "metal": ("metal", "rebar", "steel"),
                           "fabric": ("fabric", "cloth"), "packaging": ("box", "carton", "pallet"),
                           "other": ("bottle", "bag", "lamp", "toy", "book", "item")}.items():
            if any(w in blob for w in words):
                cat = key
                break
    spec = CATEGORIES.get(cat) if cat else None
    return {
        "category": cat, "confidence": 0.5 if cat else 0.0,
        "description": f"Looks like {spec.label.lower()}." if spec else "Couldn't identify the item.",
        "condition": "good" if spec and not spec.perishable else None,
        "reuse_ideas": [{"title": t, "difficulty": "easy", "steps": []} for t in (spec.reuse_ideas[:3] if spec else [])],
    }


async def analyze(images: list[bytes], hint_category: str | None = None, manufacturer_color: str | None = None,
                  notes: str | None = None, filenames: list[str] | None = None) -> VisionResult:
    provider = settings.vision_provider.lower()
    if provider == "mock":
        return clean(mock(hint_category, filenames), "mock")
    prompt = build_prompt(hint_category, manufacturer_color, notes)
    encoded = [_prep(b) for b in images[:4]]
    try:
        call = {"groq": _groq, "gemini": _gemini, "ollama": _ollama}.get(provider)
        if call is None:
            raise RuntimeError(f"unknown VISION_PROVIDER '{provider}'")
        raw = await call(prompt, encoded)
        return clean(raw, provider)
    except (httpx.HTTPError, RuntimeError, KeyError, IndexError, ValueError, ValidationError) as e:
        log.warning("vision provider %s failed: %s", provider, e)
        result = clean(mock(hint_category, filenames), "mock")
        result.warnings.append(f"The {provider} AI was unavailable ({type(e).__name__}), so this is a basic guess. Check the details.")
        return result
