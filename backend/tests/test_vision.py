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
    assert sum(1 for c in seen["body"]["messages"][0]["content"] if c["type"] == "image_url") == 3
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
