"""Create (or find) the "Food Rescue" form in your Vakh account and save its ID to .env.

    python -m scripts.vakh_login     # once
    python -m scripts.vakh_setup     # safe to re-run: reuses the form if it already exists

After this, open the form in the Vakh app and set Access -> Public access -> Read, so NGOs can
see and follow it (MCP can't change sharing; that stays a human action in Vakh).
"""
from __future__ import annotations

import asyncio
import re
import sys
import uuid
from pathlib import Path

from app.services import vakh

FORM_NAME = "Food Rescue · Waste2Worth"
DIETS = [("veg", "Veg", "green"), ("non_veg", "Non-veg", "red"), ("egg", "Egg", "yellow"),
         ("vegan", "Vegan", "green"), ("jain", "Jain", "orange")]

FIELDS = [
    {"field_id": "title", "name": "Title", "type": "string", "required": True,
     "metadata": {"inputType": "single"}},
    {"field_id": "restaurant", "name": "Restaurant", "type": "string", "required": True,
     "metadata": {"inputType": "single"}},
    {"field_id": "dish", "name": "Dish", "type": "string", "metadata": {"inputType": "single"}},
    {"field_id": "quantity", "name": "Quantity", "type": "number", "required": True,
     "metadata": {"allowDecimal": False}},
    {"field_id": "unit", "name": "Unit", "type": "string", "metadata": {"inputType": "single"}},
    {"field_id": "diet", "name": "Diet", "type": "option",
     "metadata": {"max": 1, "displayStyle": "pills", "allowCustom": False,
                  "options": [{"id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"w2w-diet-{v}")), "label": label, "value": v}
                              for v, label, _ in DIETS]}},
    {"field_id": "cooked_at", "name": "Cooked at", "type": "datetime", "metadata": {"precision": "minute"}},
    {"field_id": "pickup_by", "name": "Pick up before", "type": "datetime", "required": True,
     "metadata": {"precision": "minute"}},
    {"field_id": "location", "name": "Where", "type": "place"},
    {"field_id": "details", "name": "Details", "type": "longform"},
    {"field_id": "listing_link", "name": "Claim on Waste2Worth", "type": "url"},
]


def _text(result: dict) -> str:
    return " ".join(c.get("text", "") for c in result.get("content", []) if c.get("type") == "text")


def _find_id(result: dict) -> str | None:
    sc = result.get("structuredContent") or {}
    for obj in (sc, sc.get("form") or {}, sc.get("data") or {}):
        if isinstance(obj, dict) and obj.get("id"):
            return str(obj["id"])
    m = re.search(r'"id"\s*:\s*"([0-9a-f-]{36})"', _text(result))
    return m.group(1) if m else None


def _save_env(key: str, value: str) -> None:
    env = Path(".env")
    lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            break
    else:
        lines.append(f"{key}={value}")
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main() -> None:
    existing = await vakh.call_tool("list_forms", {"search": "Food Rescue", "limit": 20})
    forms = (existing.get("structuredContent") or {}).get("forms") or (existing.get("structuredContent") or {}).get("items") or []
    match = next((f for f in forms if f.get("name") == FORM_NAME), None)
    if match:
        form_id = str(match["id"])
        print(f"Found the existing form: {FORM_NAME} ({form_id})")
    else:
        created = await vakh.call_tool("create_form", {
            "name": FORM_NAME,
            "description": "Surplus cooked food from restaurants, posted automatically by Waste2Worth. "
                           "Verified NGOs: claim on Waste2Worth before the pickup time.",
            "fields": FIELDS,
        })
        if created.get("isError"):
            raise SystemExit(f"Vakh rejected the form: {_text(created)[:800]}")
        form_id = _find_id(created)
        if not form_id:
            raise SystemExit(f"Form created but its ID wasn't in the response:\n{created}")
        print(f"Created the form: {FORM_NAME} ({form_id})")

    _save_env("VAKH_POST_TOOL", "create_post")
    _save_env("VAKH_FOOD_FORM_ID", form_id)
    print("Saved VAKH_POST_TOOL and VAKH_FOOD_FORM_ID to .env. Restart the backend to pick them up.")
    print("Next: in the Vakh app, open the form -> Access -> set Public access to Read.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except vakh.NotConfigured as e:
        sys.exit(str(e))
    except vakh.VakhError as e:
        sys.exit(f"Vakh error: {e}")
