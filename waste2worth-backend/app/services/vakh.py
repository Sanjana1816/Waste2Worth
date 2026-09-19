"""Minimal MCP client for Vakh (streamable HTTP + OAuth bearer token).

Vakh exposes forms, posts and badges through MCP at https://xo.vakh.com/mcp. We use it to
publish each food-rescue listing as a post on a public "Food Rescue" form that NGOs follow.
Get a token once with `python -m scripts.vakh_login`; it is refreshed automatically.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

from app.config import settings

PROTOCOL_VERSION = "2025-06-18"


class NotConfigured(RuntimeError):
    pass


class VakhError(RuntimeError):
    pass


def _load_tokens() -> dict:
    p = Path(settings.vakh_token_file)
    if not p.exists():
        raise NotConfigured("Vakh is not connected. Run `python -m scripts.vakh_login` first.")
    return json.loads(p.read_text())


async def _access_token(client: httpx.AsyncClient) -> str:
    tok = _load_tokens()
    if tok.get("expires_at", 0) - 60 > time.time():
        return tok["access_token"]
    if not tok.get("refresh_token"):
        raise NotConfigured("The Vakh token has expired. Run `python -m scripts.vakh_login` again.")
    r = await client.post(tok["token_endpoint"], data={
        "grant_type": "refresh_token", "refresh_token": tok["refresh_token"], "client_id": tok["client_id"],
        "resource": tok.get("resource", "https://xo.vakh.com"),
    })
    if r.status_code >= 400:
        raise NotConfigured(f"Couldn't refresh the Vakh token ({r.status_code}). Run the login script again.")
    new = r.json()
    tok.update(access_token=new["access_token"], expires_at=time.time() + int(new.get("expires_in", 3600)))
    if new.get("refresh_token"):
        tok["refresh_token"] = new["refresh_token"]
    Path(settings.vakh_token_file).write_text(json.dumps(tok, indent=2))
    return tok["access_token"]


def _parse(resp: httpx.Response, want_id: int) -> dict:
    ctype = resp.headers.get("content-type", "")
    if "text/event-stream" in ctype:
        for line in resp.text.splitlines():
            if line.startswith("data:"):
                msg = json.loads(line[5:].strip())
                if msg.get("id") == want_id:
                    return msg
        raise VakhError("no response in event stream")
    return resp.json()


class VakhSession:
    def __init__(self, client: httpx.AsyncClient, token: str):
        self.client, self.token, self.session_id, self._id = client, token, None, 0

    async def _post(self, payload: dict) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": PROTOCOL_VERSION}
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        r = await self.client.post(settings.vakh_mcp_url, json=payload, headers=headers)
        if r.status_code == 401:
            raise NotConfigured("Vakh rejected the token. Run `python -m scripts.vakh_login` again.")
        r.raise_for_status()
        return r

    async def request(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        r = await self._post({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}})
        msg = _parse(r, self._id)
        if "error" in msg:
            raise VakhError(msg["error"].get("message", str(msg["error"])))
        return msg["result"]

    async def initialize(self) -> dict:
        self._id += 1
        r = await self._post({"jsonrpc": "2.0", "id": self._id, "method": "initialize", "params": {
            "protocolVersion": PROTOCOL_VERSION, "capabilities": {},
            "clientInfo": {"name": "waste2worth", "version": "0.1"}}})
        self.session_id = r.headers.get("mcp-session-id")
        result = _parse(r, self._id)["result"]
        await self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return result


async def _with_session(fn):
    async with httpx.AsyncClient(timeout=30) as client:
        s = VakhSession(client, await _access_token(client))
        await s.initialize()
        return await fn(s)


async def list_tools() -> list[dict]:
    result = await _with_session(lambda s: s.request("tools/list"))
    return result.get("tools", [])


async def call_tool(name: str, arguments: dict) -> dict:
    return await _with_session(lambda s: s.request("tools/call", {"name": name, "arguments": arguments}))


def food_post_arguments(listing, seller_name: str, pickup_by_ist: str) -> dict:
    """Arguments for the Vakh post tool. Check the real schema via GET /api/integrations/vakh/tools
    and adjust these keys to match it. Vakh forms have Text, Number, Place and Date & Time fields."""
    a = listing.attributes or {}
    return {
        "form_id": settings.vakh_food_form_id,
        "fields": {
            "Title": listing.title,
            "Restaurant": seller_name,
            "Plates": listing.quantity_available,
            "Diet": a.get("diet"),
            "Pickup by": pickup_by_ist,
            "Where": {"lat": listing.lat, "lng": listing.lng},
            "Details": listing.reason_detail,
        },
    }


async def publish_food(listing, seller_name: str, pickup_by_ist: str) -> dict:
    if not (settings.vakh_post_tool and settings.vakh_food_form_id):
        raise NotConfigured("Set VAKH_POST_TOOL and VAKH_FOOD_FORM_ID (see the README).")
    return await call_tool(settings.vakh_post_tool, food_post_arguments(listing, seller_name, pickup_by_ist))
