# Waste2Worth

**Reuse · Recycle · Resell · Donate.** Snap a photo of any waste. The AI identifies it, clear rules price it,
and it goes down the route that wastes least, to someone nearby who can use it.

```
w2w/
  backend/    FastAPI + SQLModel: listings, photo checks, pooled lots, food rescue, AI & voice   → Railway
  frontend/   React + Vite: the web app                                                         → Vercel
              Database and photo storage                                                        → Supabase
```

## Run it on your laptop

You need Python 3.12+ and Node 20+.

**Backend** (terminal 1):
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m scripts.seed --reset
uvicorn app.main:app --reload
```
API docs: http://localhost:8000/docs · tests: `pytest`

**Frontend** (terminal 2):
```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```
App: http://localhost:5173

Everything runs with **no API keys**: the vision AI falls back to a basic built-in guess, photos are stored on disk,
NGO calls and Vakh posts are logged as "simulated", and "Listen" uses the browser's own voice.
Add keys to `backend/.env` to switch each one on. See [DEPLOY.md](DEPLOY.md).

## Demo script (3 minutes)

Use the **Acting as** menu (top right) to switch between the demo accounts.

1. **List waste** as *Sharma Interiors*: add photos → AI identifies them → the form adapts to tiles (brand, design code,
   manufacturer's colour, reason for disposal) → required proof photos with instant quality checks (try a blurry one)
   → the white-sheet photo gives the true colour → publish.
2. **Pooled lots** as *Ravi Renovations*: 200 tiles → 3 sellers pooled, and the other batch is excluded by its colour
   difference (ΔE) → 33% below new → reserve → confirm.
3. **Food rescue** as *Spice Route Kitchen*: speak "Chalis plates veg biryani bache hain…" → confirm → 2 photos
   → publish → the ElevenLabs agent rings the NGO (your phone, see DEPLOY.md) → switch to *Full Plate Foundation*
   and claim it.
4. **Impact**: live totals and a printable CSR certificate for the restaurant.

## What's where

| Feature | Backend | Frontend |
|---|---|---|
| Category forms (fields, photos, reasons, provenance) | `app/catalog.py` | `pages/Sell.jsx` |
| Photo quality + lighting-corrected colour | `app/services/imaging.py` | `pages/Sell.jsx` (photo step) |
| Pricing, price cap, commission | `app/services/valuation.py` | review step, receipts |
| Route recommendation | `app/services/routing.py` | review step |
| Pooled lots / orders | `app/services/pooling.py` | `pages/Pool.jsx`, `pages/ListingDetail.jsx` |
| Food rescue, NGO calls, Vakh | `app/services/dispatch.py`, `voice.py`, `vakh.py` | `pages/Food.jsx` |
| Vision AI (Groq / Gemini / Ollama / mock) | `app/services/vision.py` | Snap step |
| Impact + certificate | `app/routers/meta.py` | `pages/Impact.jsx` |

The demo accounts are a stand-in for login. Before a real launch, add Supabase Auth and check permissions on every write.
