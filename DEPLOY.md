# DaamKoto — Free Deployment Guide

The whole stack runs on free tiers:

| Piece | Host | Cost |
|---|---|---|
| Frontend (React) | **Vercel** | Free — ✅ already live at https://daamkoto.vercel.app |
| Database (PostgreSQL) | **Neon** | Free (0.5 GB, never expires) |
| Backend API (FastAPI) | **Render** | Free web service |
| Scrapers (Playwright) | **Your PC** | Free — run locally, push data up |

> Why scrapers stay local: Playwright needs a headless browser that free cloud
> tiers won't run reliably. You scrape on your PC and the data lands in Neon,
> which the hosted API reads. The scrapers' `DATABASE_URL` just points at Neon.

The code is already prepared for all of this (see commits `5036bec`, `b2bd4a0`):
- `backend/database.py` reads a single `DATABASE_URL` when present
- `backend/requirements.txt` — slim, API-only deps
- `render.yaml` — Render blueprint
- CORS already allows `*` origins

---

## Step 1 — Database on Neon (~5 min)

1. Sign up at **https://neon.tech** (use "Continue with GitHub").
2. Create a project — name it `daamkoto`, pick the region closest to you
   (Singapore is nearest to Bangladesh).
3. On the project dashboard, copy the **connection string**. It looks like:
   ```
   postgresql://USER:PASSWORD@ep-xxxx-pooler.REGION.aws.neon.tech/neondb?sslmode=require
   ```
   Use the **pooled** ("-pooler") string. Save it — this is your `DATABASE_URL`.

### Load your data into Neon
Your local DB (19,769 products / 79,847 prices) was exported to
`daamkoto_db_dump.sql` (gitignored — it stays on your PC).

Run this from the project folder (PowerShell), pasting your Neon string:
```powershell
$env:NEON = "postgresql://USER:PASSWORD@ep-xxxx-pooler...neon.tech/neondb?sslmode=require"
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" $env:NEON -f daamkoto_db_dump.sql
```
This recreates the schema + all data in Neon. (Re-run later to refresh, or just
point the scrapers at Neon — see Step 4.)

---

## Step 2 — Backend on Render (~5 min)

1. Sign up at **https://render.com** (Continue with GitHub).
2. **New → Blueprint** → connect the `daamkoto` repo → Render reads `render.yaml`.
3. It creates a web service `daamkoto-api`. Before the first deploy, set the two
   secret env vars (Render → service → **Environment**):
   - `DATABASE_URL` = your Neon pooled connection string (from Step 1)
   - `GROQ_API_KEY` = from https://console.groq.com (free; "Create API Key")
4. Deploy. When it's live you'll get a URL like
   `https://daamkoto-api.onrender.com`. Test it:
   `https://daamkoto-api.onrender.com/health` → should return `{"status":"ok"}`.

> ⚠️ Render free tier **sleeps after 15 min idle**; the first request after that
> takes ~30–50 s to wake. Normal for free — just a cold-start delay.

---

## Step 3 — Connect frontend → backend (~2 min)

1. Vercel → project `daamkoto` → **Settings → Environment Variables**.
2. Add: `VITE_API_BASE` = `https://daamkoto-api.onrender.com`
   (your Render URL, **no trailing slash**). Apply to **Production**.
3. **Deployments** tab → latest → ⋯ → **Redeploy**.

Done — https://daamkoto.vercel.app now shows live products. 🎉

---

## Step 4 — Keep data fresh (optional, ongoing)

To scrape and push straight into Neon, set the same `DATABASE_URL` in your local
`.env`, then run the pipeline as usual:
```powershell
.\venv\Scripts\Activate.ps1
# In .env add: DATABASE_URL=postgresql://...neon.tech/neondb?sslmode=require
python scheduler.py --once          # one sweep of all categories
```
The loader writes to whatever `DATABASE_URL` points at. Remove that line from
`.env` to go back to writing your local DB.

---

## Recap of credentials you'll create
- Neon account → `DATABASE_URL`
- Groq account → `GROQ_API_KEY`
- (GitHub + Vercel already done)

All free, no card required.
