import asyncio
import json as json_mod

import httpx

from app.config import settings
from app.services import vision
from scripts.synth import photo


def test_groq_request_and_parsing(monkeypatch):
    seen = {}

    async def fake_post(self, url, json=None, headers=None, **kw):
        seen.update(url=url, body=json, headers=headers)
        content = {"category": "tiles", "confidence": 0.91, "condition": "good", "visible_color_name": "off-white",
                   "color_matches_manufacturer": "yes",
                   "suggested_attributes": {"finish": "Matte", "material": "vitrified", "bogus": 1},
                   "reuse_ideas": [{"title": "Mosaic path", "difficulty": "easy", "steps": ["Break", "Lay"]}]}
        return httpx.Response(200, request=httpx.Request("POST", url),
                              json={"choices": [{"message": {"content": json_mod.dumps(content)}}]})

    monkeypatch.setattr(settings, "vision_provider", "groq")
    monkeypatch.setattr(settings, "groq_api_key", "test-key")
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    r = asyncio.run(vision.analyze([photo((230, 230, 225))] * 4, manufacturer_color="Arctic Matte White"))

    assert seen["url"].endswith("/openai/v1/chat/completions")
    assert seen["body"]["reasoning_effort"] == "none" and seen["body"]["response_format"] == {"type": "json_object"}
    # only 2 images are sent: each costs ~2048 tokens against Groq's 8000/minute free limit
    assert sum(1 for c in seen["body"]["messages"][0]["content"] if c["type"] == "image_url") == 2
    assert r.provider == "groq" and r.category == "tiles"
    assert r.suggested_attributes == {"finish": "matte", "material": "vitrified"}


def test_provider_failure_falls_back_to_mock(monkeypatch):
    async def boom(self, url, **kw):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(settings, "vision_provider", "groq")
    monkeypatch.setattr(settings, "groq_api_key", "test-key")
    monkeypatch.setattr(httpx.AsyncClient, "post", boom)
    r = asyncio.run(vision.analyze([photo((200, 100, 90))], hint_category="tiles"))
    assert r.provider == "mock" and r.category == "tiles" and r.warnings


def test_rate_limit_is_retried_with_one_image(monkeypatch):
    calls = []

    async def fake_post(self, url, json=None, headers=None, **kw):
        req = httpx.Request("POST", url)
        images = [c for c in json["messages"][0]["content"] if c["type"] == "image_url"]
        calls.append(len(images))
        if len(calls) == 1:                      # first try: Groq says "too many tokens this minute"
            raise httpx.HTTPStatusError("429", request=req,
                                        response=httpx.Response(429, request=req, headers={"retry-after": "0"}))
        content = {"category": "other", "confidence": 0.7, "condition": "good"}
        return httpx.Response(200, request=req, json={"choices": [{"message": {"content": json_mod.dumps(content)}}]})

    monkeypatch.setattr(settings, "vision_provider", "groq")
    monkeypatch.setattr(settings, "groq_api_key", "test-key")
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    r = asyncio.run(vision.analyze([photo((200, 150, 120))] * 2))

    assert calls == [2, 1]                       # retried with a single image
    assert r.provider == "groq" and r.category == "other" and not r.warnings


def test_persistent_rate_limit_explains_itself(monkeypatch):
    async def always_429(self, url, **kw):
        req = httpx.Request("POST", url)
        raise httpx.HTTPStatusError("429", request=req,
                                    response=httpx.Response(429, request=req, headers={"retry-after": "0"}))

    monkeypatch.setattr(settings, "vision_provider", "groq")
    monkeypatch.setattr(settings, "groq_api_key", "test-key")
    monkeypatch.setattr(httpx.AsyncClient, "post", always_429)
    r = asyncio.run(vision.analyze([photo((200, 150, 120))], hint_category="tiles"))
    assert r.provider == "mock" and "busy" in r.warnings[0]
