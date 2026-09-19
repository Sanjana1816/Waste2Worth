# Waste2Worth backend

FastAPI backend for Waste2Worth: **reuse · recycle · resell · donate**.
Snap a photo of any waste; the API identifies it, checks the photos, values it, picks the best route and
finds who nearby can use it. It also pools identical stock from many sellers into one order and rescues
surplus food through verified NGOs.

## Run it

```bash
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt
copy .env.example .env
python -m scripts.seed --reset                       # demo data: 15 orgs, 13 listings, all fictional
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs for interactive API docs. `pytest` runs 22 tests.

Everything works with no API keys: the vision AI falls back to a mock, and NGO calls and Vakh posts are
logged as `simulated`. Add keys in `.env` to switch each one on.

## How a listing works

1. `GET /api/categories/{key}`: the form spec for the category. It covers the fields, required photos, the minimum
   photo count, the "why is this waste?" reasons and the required provenance fields. **The frontend builds the form from this.**
2. `POST /api/ai/analyze` (optional): photos → suggested category, condition, attributes, colour check and reuse ideas.
3. `POST /api/listings`: creates a draft. The response gives field errors (422) or readiness: which photos are missing.
4. `POST /api/listings/{id}/images` (`shot_type` + `file`): each photo is checked for size, blur, exposure,
   and (for the colour-reference shot) the colour after lighting correction. Bad photos come back with a retake hint.
5. `POST /api/listings/{id}/publish`: only works once every required photo passes. Food listings immediately
   alert the nearest verified NGOs.

### What sellers must provide

| Requirement | Why |
|---|---|
| **Reason for disposal** (`reason_code` + at least 15 characters of `reason_detail`) | Builds trust; e.g. "Client switched to wooden flooring" |
| **Provenance**: brand, product name, SKU/design code, **manufacturer's colour name**, where bought, year | Pooling matches on these; buyers know exactly what they get |
| **Category-specific fields**: tile size, finish and batch/shade code; device working status and data wiped; food cooked-at time and storage... | Defined per category in `app/catalog.py` |
| **Minimum photos with named shots** (tiles: 4: whole lot, surface, box label, colour reference) | No listing without evidence |

### Lighting and colour

The same tile looks warmer under a bulb and bluer in shade. For colour-critical categories (tiles, fabric,
clothing) the **colour-reference shot** has the item in the middle of a plain white A4 sheet. The sheet is a
known white, so the API cancels out the lighting's colour and brightness before measuring the item's colour
(CIELAB). Pooling then compares lots by colour difference (ΔE); a different batch (ΔE > 6) is excluded.
A blown-out sheet is rejected with a retake hint, because clipped pixels can't be corrected.
The manufacturer's colour name remains the primary match key, and the photo check catches mismatched batches.

## Main endpoints

| | |
|---|---|
| `GET /api/listings?category=&route=&lat=&lng=&radius_km=&q=` | Search with distance |
| `GET /api/listings/{id}/matches` | Nearby buyers / certified recyclers / verified NGOs, depending on the route |
| `POST /api/pools/quote` | Pooled-lot preview: by `listing_id`, or demand-first by `category` + `match` |
| `POST /api/pools` → `/confirm` / `/cancel` | All-or-nothing reservation (30 min) |
| `POST /api/food/voice-draft` | Audio → ElevenLabs speech-to-text → food listing draft |
| `POST /api/food/text-draft` | Same parser without audio (English / Hinglish) |
| `POST /api/listings/{id}/claim` | A verified NGO claims a donation |
| `POST /api/ai/speak` | ElevenLabs TTS (e.g. read reuse ideas aloud) → mp3 |
| `GET /api/impact/summary`, `/api/impact/orgs/{id}/certificate` | Impact numbers and a CSR certificate |
| `GET /api/integrations/status`, `/api/integrations/vakh/tools` | Which integrations are live |

## Business rules (all in code, all tested)

- Resale price is capped below the new price: 85% (new) down to 25% (poor); brand seconds at 70% of MRP.
- Commission: 10% under ₹2k, 8% under ₹20k, 6% under ₹1L, then 5%. ₹49 extra for multi-seller pools. Donations: 0%.
- A pool is refused if, after pickup and fees, it costs 90% or more of the new price.
- Brand seconds: brand accounts only; cosmetic defects only; defect close-up photo required; MRP required.
- Laptops, phones and tablets must be data-wiped before resale or donation. E-waste recycling is matched only to certified recyclers.
- Cooked food is always free, must have a cooked-at time, and expires 4 h after cooking (24 h if refrigerated).
  Only verified NGOs can claim it. Uploaded photos are re-encoded, which strips GPS/EXIF data.

## Integrations

**Vision.** `VISION_PROVIDER=gemini` with a free key from Google AI Studio (fast, recommended for the demo), or
`ollama` with `ollama pull gemma3:4b` (offline, but ~30–60 s per photo on a laptop CPU). If either fails, the
API falls back to the mock and says so in `warnings`. The AI never sets prices.

**ElevenLabs.** `ELEVENLABS_API_KEY` enables speech-to-text and text-to-speech. For real NGO phone calls, create a
Conversational AI agent (prompt using `{{dish}} {{plates}} {{restaurant}} {{distance_km}} {{pickup_by}}`), connect
a Twilio number to it, then set `ELEVENLABS_AGENT_ID` and `ELEVENLABS_PHONE_NUMBER_ID`. A Twilio trial can only
call verified numbers, which is enough to ring your own phone on stage.

**Vakh.** Vakh exposes forms and posts over MCP with OAuth. To connect:
1. In the Vakh app, create a public form "Food Rescue · Bengaluru" with fields: Title, Restaurant, Plates (Number),
   Diet, Pickup by (Date & Time), Where (Place), Details.
2. `python -m scripts.vakh_login` signs in through your browser and saves the tokens.
3. `GET /api/integrations/vakh/tools` shows Vakh's real tool names and input schemas. Set `VAKH_POST_TOOL`,
   `VAKH_FOOD_FORM_ID`, and adjust `food_post_arguments()` in `app/services/vakh.py` to match the schema.
   (This last step is untested: the argument shape is a best guess until you see the schema.)

## Layout

```
app/
  catalog.py        categories: fields, photos, reasons, price/CO2 factors   <- add categories here
  models.py         Org, Listing, ListingImage, Pool, PoolItem, Claim, DispatchLog
  services/         validation, imaging, valuation, impact, routing, pooling, vision, voice, vakh, dispatch
  routers/          listings, pools, donations, ai, meta
scripts/            seed, synth (synthetic photos), vakh_login
tests/              imaging, validation, API flows
```
