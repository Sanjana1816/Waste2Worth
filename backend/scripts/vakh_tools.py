"""List the tools Vakh's MCP server offers (names, descriptions, input schemas).

    python -m scripts.vakh_login     # once, signs you in
    python -m scripts.vakh_tools     # writes vakh_tools.json and prints a summary

Share vakh_tools.json (it contains no secrets) so the form-creation and posting calls
can be matched to Vakh's real tool names and arguments.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.services import vakh


async def main() -> None:
    try:
        tools = await vakh.list_tools()
    except vakh.NotConfigured as e:
        raise SystemExit(str(e))
    Path("vakh_tools.json").write_text(json.dumps(tools, indent=2))
    print(f"Vakh offers {len(tools)} tools (full details saved to vakh_tools.json):\n")
    for t in tools:
        print(f"- {t['name']}: {(t.get('description') or '').strip().splitlines()[0][:100] if t.get('description') else ''}")


if __name__ == "__main__":
    asyncio.run(main())
