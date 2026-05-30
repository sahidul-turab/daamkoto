# DaamKoto — Deployment & Update Guide

The whole stack runs on free tiers and is **live**:

| Piece | Host | URL |
|---|---|---|
| Frontend (React) | **Vercel** | https://daamkoto.vercel.app |
| Backend API (FastAPI) | **Render** | https://daamkoto-api.onrender.com |
| Database (PostgreSQL) | **Neon** | (private connection string) |
| Scrapers (Playwright) | **Your PC** | run locally, push data to Neon |

**Key fact:** Vercel and Render both **auto-deploy on every `git push` to `main`.**
So most updates are just a commit + push — no dashboard clicking.

---

## Updating the live site

### Case A — Code change (frontend or backend) — *90% of updates*
Edit + test locally, then:
```powershell
git add -A
git commit -m "describe your change"
git push
```
- Vercel rebuilds the frontend (~1 min)
- Render rebuilds the backend (~2–3 min)

That's the entire process. Nothing else needed.

> Reminder: frontend env vars (like `VITE_API_BASE`) are baked in at **build
> time**. If you change one in Vercel, you must redeploy for it to take effect.

### Case B — New scraped data (prices changed, code unchanged)
You scraped fresh prices into your **local** DB and want them live. Pick one:

**Simplest — scrape straight into Neon:**
```powershell
.\venv\Scripts\Activate.ps1
# Temporarily add to .env:  DATABASE_URL=<neon pooled connection string>
python scheduler.py --once
# Remove the DATABASE_URL line from .env to go back to writing the local DB.
```

**Or — full refresh (export local → reload Neon):**
```powershell
$PG = "C:\Program Files\PostgreSQL\17\bin"
& "$PG\pg_dump.exe" -h localhost -U postgres -d pc_comparison `
    --no-owner --no-privileges -f daamkoto_db_dump.sql
& "$PG\psql.exe" "<neon-url>" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
& "$PG\psql.exe" "<neon-url>" -f daamkoto_db_dump.sql
```

After loading data, refresh the materialized view so current prices update:
```powershell
& "$PG\psql.exe" "<neon-url>" -c "REFRESH MATERIALIZED VIEW mv_current_prices;"
```

### Case C — Database schema change (new table / column / migration)
1. Run the migration against Neon:
   ```powershell
   & "C:\Program Files\PostgreSQL\17\bin\psql.exe" "<neon-url>" -f database/migration_xxx.sql
   ```
2. Push the code that uses it (Case A).

---

## How Claude can help (just ask in a session)

Vercel/Render auto-deploy on push, so Claude can do almost everything from the
CLI. Typical requests:

| You say | Claude does |
|---|---|
| "Deploy my changes" | Reviews the local diff, commits, pushes (triggers Vercel + Render), then verifies the live site |
| "Push new prices to live" | Syncs local DB → Neon, refreshes the materialized view, checks counts |
| "I added a migration" | Applies it to Neon, pushes the code, smoke-tests live endpoints |
| "Is the live site OK?" | Runs health + data checks against the live URLs and reports |

Claude **cannot** click buttons in the Vercel/Render dashboards or log into your
accounts — but with auto-deploy it rarely needs to.

---

## Health checks (verify the live chain)
```powershell
# Backend up? (cold start can take ~30–50s on Render free tier)
Invoke-RestMethod "https://daamkoto-api.onrender.com/health"          # {"status":"ok"}

# Live data flowing?
(Invoke-RestMethod "https://daamkoto-api.onrender.com/products?category=GPU").total

# Frontend serving DaamKoto?
(Invoke-WebRequest "https://daamkoto.vercel.app" -UseBasicParsing).Content -match "<title>DaamKoto"
```

> ⚠️ Render free tier **sleeps after ~15 min idle**; the first request wakes it
> (~30–50s). Normal — not a bug.

---

## Environment variables (where secrets live)

**Render** (`daamkoto-api` → Environment):
- `DATABASE_URL` — Neon pooled connection string (`...-pooler...?sslmode=require`)
- `GROQ_API_KEY` — from https://console.groq.com (free; chatbot LLM)
- `FRONTEND_ORIGIN` — `https://daamkoto.vercel.app` (set via render.yaml)

**Vercel** (project → Settings → Environment Variables):
- `VITE_API_BASE` — `https://daamkoto-api.onrender.com` (no trailing slash)

**Local** (`.env`, gitignored):
- `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` — local Postgres
- `GROQ_API_KEY` — for running the chatbot locally
- `DATABASE_URL` — *optional*, only when you want local scrapers to write to Neon

> `backend/database.py` prefers `DATABASE_URL` when set, else falls back to the
> discrete `DB_*` vars. So the same code runs locally and in the cloud.

---

## Initial setup (already done — for reference / rebuilding)

<details>
<summary>One-time provisioning steps</summary>

**Neon (database)**
1. Sign up at https://neon.tech (Continue with GitHub).
2. Create project `daamkoto`, region Singapore (`ap-southeast-1`, nearest to BD).
3. Copy the **pooled** connection string → this is `DATABASE_URL`.
4. Load data: `psql "<neon-url>" -f daamkoto_db_dump.sql`
5. `ALTER ROLE neondb_owner SET search_path TO public;` (so the API finds tables)

**Render (backend)**
1. Sign up at https://render.com (Continue with GitHub).
2. New → Blueprint → pick the `daamkoto` repo (reads `render.yaml`) → Apply.
3. Set `DATABASE_URL` and `GROQ_API_KEY` in the service's Environment tab.
4. Test `https://daamkoto-api.onrender.com/health`.

**Vercel (frontend)**
1. Import the repo; set **Root Directory = `frontend-react`**, Framework = Vite.
2. Add env var `VITE_API_BASE = https://daamkoto-api.onrender.com`.
3. Redeploy.
</details>

---

## Security note
If a `DATABASE_URL` / API key is ever exposed (e.g. pasted in chat), rotate it:
- **Neon**: dashboard → Settings/Roles → Reset password → update `DATABASE_URL`
  in Render → it auto-redeploys.
- **Groq**: console → API Keys → revoke + create → update `GROQ_API_KEY` in Render.
