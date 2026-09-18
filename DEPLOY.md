# Keys and deployment

Order: **1. get keys → 2. Supabase → 3. push to GitHub → 4. Railway (backend) → 5. Vercel (frontend) → 6. seed → 7. extras.**
All of it fits in free tiers. Allow about an hour.

---

## 1. Keys you need

| Key | Needed? | Where to get it | Goes in |
|---|---|---|---|
| **Groq API key** | Yes (vision AI) | https://console.groq.com → *API Keys* → *Create API Key* | `GROQ_API_KEY` |
| **Supabase** URL, secret key, DB connection string | Yes (production) | Step 2 below | `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `DATABASE_URL` |
| **ElevenLabs API key** | For voice | https://elevenlabs.io → profile → *API Keys* → *Create*. Give it access to Speech to Text, Text to Speech and Agents | `ELEVENLABS_API_KEY` |
| ElevenLabs agent ID + phone number ID | For the live NGO call | Step 7a | `ELEVENLABS_AGENT_ID`, `ELEVENLABS_PHONE_NUMBER_ID` |
| Twilio account | For the live NGO call | https://www.twilio.com/try-twilio (free trial credit) | Connected inside ElevenLabs |
| Vakh account + tokens | For the Vakh bonus | Step 7b | `VAKH_TOKENS_JSON`, `VAKH_POST_TOOL`, `VAKH_FOOD_FORM_ID` |

Never commit keys. `.env` files are git-ignored; in production, keys go into Railway / Vercel variables.

---

## 2. Supabase (database + photo storage)

1. https://supabase.com → **New project**. Pick the Mumbai (`ap-south-1`) region and save the database password.
2. **Database connection string:** click **Connect** (top bar) → **Session pooler** → copy the URI. It looks like
   `postgresql://postgres.<ref>:[YOUR-PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:5432/postgres`
   Replace `[YOUR-PASSWORD]`. If the password has symbols like `@ # /`, URL-encode them (`@` → `%40`), or reset the
   password to letters and numbers.
   *Use the Session pooler, not "Direct connection": the direct host is IPv6-only and Railway can't reach it.*
3. **Photo bucket:** *Storage* → **New bucket** → name `listing-photos` → turn on **Public bucket** → *Create*.
4. **Keys:** *Project Settings → API Keys*. Copy the **Project URL** (`https://<ref>.supabase.co`) and a **secret key**
   (`sb_secret_...`; the legacy `service_role` key also works). The secret key stays on the backend only, never in the frontend.

The backend creates its tables on first start; no SQL needed.

---

## 3. Push to GitHub

```bash
cd D:\w2w
git init
git add .
git commit -m "Waste2Worth"
```
Create an empty repo on GitHub (no README), then:
```bash
git remote add origin https://github.com/<you>/waste2worth.git
git branch -M main
git push -u origin main
```
Check that `backend/.env` and `frontend/.env` are **not** in the commit (`git status` shouldn't list them).

---

## 4. Railway (backend)

1. https://railway.com → **New Project** → **Deploy from GitHub repo** → pick the repo.
2. Click the service → **Settings**:
   - **Root Directory:** `backend`
   - The start command and health check come from `backend/railway.json`.
3. **Variables** tab → *Raw Editor* → paste and fill in:
   ```
   DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
   STORAGE_BACKEND=supabase
   SUPABASE_URL=https://<ref>.supabase.co
   SUPABASE_SECRET_KEY=sb_secret_...
   SUPABASE_BUCKET=listing-photos
   VISION_PROVIDER=groq
   GROQ_API_KEY=gsk_...
   ELEVENLABS_API_KEY=
   CORS_ORIGINS=["http://localhost:5173"]
   CORS_ORIGIN_REGEX=https://.*\.vercel\.app
   ```
   (Replace the CORS values with your exact Vercel URL after step 5 if you want to lock it down.)
4. **Settings → Networking → Generate Domain.** You get something like `https://waste2worth-production.up.railway.app`.
5. Open `<that URL>/health`: you should see `{"ok":true}`. `<that URL>/docs` shows the API.
   `<that URL>/api/integrations/status` shows which integrations are live.

---

## 5. Vercel (frontend)

1. https://vercel.com → **Add New… → Project** → import the repo.
2. **Root Directory:** `frontend`. The framework preset (Vite) is detected automatically.
3. **Environment Variables:** `VITE_API_URL` = your Railway URL (no trailing slash).
4. **Deploy.** `frontend/vercel.json` makes page refreshes on `/explore`, `/listing/3` etc. work.
5. If you changed the frontend URL or didn't use the regex, add it to Railway's `CORS_ORIGINS`, e.g.
   `["https://waste2worth.vercel.app"]`, and redeploy the backend.

`VITE_` variables are baked in at build time, so after changing `VITE_API_URL`, redeploy on Vercel.

---

## 6. Load the demo data into production

Run the seed from your laptop, pointing it at Supabase (it uploads the demo photos to your bucket):
```bash
cd backend
.venv\Scripts\activate
set DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
set STORAGE_BACKEND=supabase
set SUPABASE_URL=https://<ref>.supabase.co
set SUPABASE_SECRET_KEY=sb_secret_...
set DEMO_NGO_PHONE=+91XXXXXXXXXX
python -m scripts.seed --reset
```
`DEMO_NGO_PHONE` is **your own mobile number**. It's given to the demo NGO "Full Plate Foundation", so the voice
agent calls you on stage. `--reset` wipes all data, so run it before the demo, not after real users sign up.

(Or with the Railway CLI: `railway link`, then `railway run python -m scripts.seed --reset` from `backend/`.)

---

## 7. Extras for bonus points

### 7a. ElevenLabs voice agent that calls NGOs
1. ElevenLabs → **Agents** → **Create agent** (blank).
   - **First message:** `Hi {{ngo}}, this is Waste2Worth. {{restaurant}}, {{distance_km}} kilometres from you, has {{plates}} of {{dish}} ready for pickup before {{pickup_by}}. Can you collect it?`
   - **System prompt:** *You are a polite food-rescue coordinator in India. Confirm whether the NGO can pick up the food
     before the deadline. Speak simply; switch to Hindi if they do. Keep the call under a minute.*
   - Choose a voice and the multilingual model. Copy the **Agent ID**.
2. Twilio: sign up, verify **your** phone number (trial accounts can only call verified numbers), buy the free trial
   number, and under *Voice → Settings → Geo permissions* enable **India**. Copy the Account SID and Auth Token.
3. ElevenLabs → **Phone Numbers** → **Import number** → Twilio → paste the number, SID and token → assign it to the
   agent. Copy the **Phone number ID**.
4. Railway variables: `ELEVENLABS_AGENT_ID`, `ELEVENLABS_PHONE_NUMBER_ID`. Publish a food listing and your phone rings.

Speech-to-text (the mic on the Food page) and "Listen" buttons only need `ELEVENLABS_API_KEY`.
The browser only allows the microphone on `https://` or `localhost`, so it works on Vercel.

### 7b. Vakh community boards
1. Sign up at https://vakh.com. Create a public form **"Food Rescue · Bengaluru"** with fields:
   Title (Text), Restaurant (Text), Plates (Number), Diet (Text), Pickup by (Date & Time), Where (Place), Details (Text).
   Create a **"Verified NGO"** badge too.
2. On your laptop: `cd backend` → `python -m scripts.vakh_login`. Your browser opens, you approve, and it saves `.vakh_tokens.json`.
3. Run the backend locally and open http://localhost:8000/api/integrations/vakh/tools. Find the tool that creates a
   post and note its **name**, its **input schema** and your form's **ID**.
4. Set `VAKH_POST_TOOL` and `VAKH_FOOD_FORM_ID`. If the schema's argument names differ from what
   `food_post_arguments()` in `backend/app/services/vakh.py` sends, adjust that one function (about 10 lines).
5. For Railway: paste the whole contents of `.vakh_tokens.json` into a `VAKH_TOKENS_JSON` variable.

This step is **untested**: the tool name and argument shape are only visible after you log in.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Frontend says "Can't reach the server" | `VITE_API_URL` is wrong or missing; redeploy on Vercel after fixing it |
| Browser console shows a CORS error | Add the exact Vercel URL to `CORS_ORIGINS` on Railway |
| Railway crashes: `could not translate host name` / timeout | Use the Supabase **Session pooler** URI, not the direct one |
| Railway error: `password authentication failed` | URL-encode special characters in the password |
| Photo upload returns 502 "Supabase upload failed" | Bucket name doesn't match `SUPABASE_BUCKET`, or the key is the publishable one instead of the secret one |
| Photos upload but don't display | The bucket isn't **Public** |
| AI result says "basic guess" | `VISION_PROVIDER=groq` and `GROQ_API_KEY` aren't both set, or the Groq rate limit was hit (it falls back automatically) |
| Listen/speech returns 503 | `ELEVENLABS_API_KEY` isn't set (the app falls back to the browser's voice) |
