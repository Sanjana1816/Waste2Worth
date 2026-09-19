"""One-time Vakh login (OAuth 2.1 + PKCE, dynamic client registration).

    python -m scripts.vakh_login

Opens your browser at Vakh's sign-in page. After you approve, the tokens are saved to
VAKH_TOKEN_FILE (default ./.vakh_tokens.json, which is git-ignored) and refreshed automatically.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import httpx

from app.config import settings

RESOURCE = "https://xo.vakh.com"
PORT = 8765
REDIRECT = f"http://127.0.0.1:{PORT}/callback"
SCOPE = "openid profile email offline_access"


def main() -> None:
    meta = httpx.get(f"{RESOURCE}/.well-known/oauth-authorization-server", timeout=15).json()
    reg = httpx.post(meta["registration_endpoint"], timeout=15, json={
        "client_name": "Waste2Worth", "redirect_uris": [REDIRECT],
        "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"],
        "token_endpoint_auth_method": "none", "scope": SCOPE,
    })
    reg.raise_for_status()
    client_id = reg.json()["client_id"]

    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    url = meta["authorization_endpoint"] + "?" + urllib.parse.urlencode({
        "response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT, "scope": SCOPE,
        "state": state, "code_challenge": challenge, "code_challenge_method": "S256", "resource": RESOURCE,
    })

    got: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>Waste2Worth is connected to Vakh. You can close this tab.</h2>")

        def log_message(self, *args):
            pass

    print("Opening Vakh sign-in in your browser...\nIf it doesn't open, visit:\n" + url)
    webbrowser.open(url)
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    while "code" not in got and "error" not in got:
        server.handle_request()
    if got.get("error") or got.get("state") != state:
        raise SystemExit(f"Login failed: {got.get('error_description') or got.get('error') or 'state mismatch'}")

    tok = httpx.post(meta["token_endpoint"], timeout=15, data={
        "grant_type": "authorization_code", "code": got["code"], "redirect_uri": REDIRECT,
        "client_id": client_id, "code_verifier": verifier, "resource": RESOURCE,
    })
    tok.raise_for_status()
    t = tok.json()
    Path(settings.vakh_token_file).write_text(json.dumps({
        "access_token": t["access_token"], "refresh_token": t.get("refresh_token"),
        "expires_at": time.time() + int(t.get("expires_in", 3600)),
        "client_id": client_id, "token_endpoint": meta["token_endpoint"], "resource": RESOURCE,
    }, indent=2))
    print(f"Saved tokens to {settings.vakh_token_file}. Next: GET /api/integrations/vakh/tools")


if __name__ == "__main__":
    main()
