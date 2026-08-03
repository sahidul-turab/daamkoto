# DaamKoto — দাম কত?

**Compare PC component prices across 15 Bangladeshi retailers, in one place.**

DaamKoto lets Bangladeshi PC buyers search for any component — RAM, GPU, SSD, CPU,
monitor, keyboard, chair — and instantly see what every major local shop charges
for it, so you find the cheapest source without tab-hopping across a dozen sites.

Prices are stored **append-only with timestamps**, so the site also shows how a
part's price moved over time — something no local competitor offers.

An **agentic AI assistant** sits on top: ask in plain language ("find me 16GB DDR5
under 6000 taka", "plan me a 80k gaming build") and it calls real database tools
to answer. The LLM understands; the database answers; **the bot never invents prices.**

---

## Live

| Piece | Host | URL |
|---|---|---|
| Frontend | Vercel | https://daamkoto.vercel.app |
| Backend API | Render | https://daamkoto-api.onrender.com ([`/docs`](https://daamkoto-api.onrender.com/docs)) |
| Database | Neon (PostgreSQL) | private connection string |
| Scrapers | GitHub Actions | daily 20:00 UTC, writes straight to Neon |

**Scale today:** ~35,000 canonical products · ~146,000 price rows · 15 retailers ·
24 live categories.

---

## Documentation map — read in this order

| Doc | What it answers |
|---|---|
| **README.md** (this file) | What is this, how do I run it |
| **[PRD.md](PRD.md)** | What the product is meant to be — users, features, scope, roadmap |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | How it is built — every stage, module, table, and data flow |
| **[IMPROVEMENTS.md](IMPROVEMENTS.md)** | What has been improved and *why* — the decision log |
| **[CLAUDE.md](CLAUDE.md)** | Operating manual for AI agents — conventions, workflows, traps |
| **[DEPLOY.md](DEPLOY.md)** | How to ship changes and keep the free tier alive |

> **If you are an AI assistant picking this project up cold:** read
> `CLAUDE.md` first (rules and traps), then `ARCHITECTURE.md` (how it works),
> then `PRD.md` (where it's going).

---

## Architecture in one table

| Stage | Folder | Tech | Job |
|---|---|---|---|
| 1. Scrape | `scrapers/` | Python + Playwright | Pull raw listings from 15 shops |
| 2. Clean & match | `cleaning/` | rapidfuzz | Normalize specs, fold duplicates into one canonical product |
| 3. Store | `database/` | PostgreSQL | Append-only prices + JSONB specs |
| 4. Serve | `backend/` | FastAPI + Uvicorn | 19 endpoints, response cache, AI agent |
| 5. Display | `frontend-react/` | React 18 + Vite 6 + Tailwind v4 | Browse / Build / Deals / Scraper views |
| 6. Images | `scripts/` | rembg + Cloudflare R2 | Background-removed product cutouts |

**AI:** Groq `llama-3.3-70b-versatile` (fast lane) + Google Gemini `2.0-flash`
(reasoning lane). Both free tiers. Not Anthropic — see `backend/llm.py`.

---

## Run locally

```powershell
# 0. One-time: copy .env.example to .env and fill in your Postgres credentials
#    (plus GROQ_API_KEY / GEMINI_API_KEY if you want the chatbot)

# 1. Activate the virtual environment (every new terminal)
.\venv\Scripts\Activate.ps1

# 2. Backend — Terminal 1
python -m uvicorn backend.main:app --reload --port 8000

# 3. Frontend — Terminal 2
cd frontend-react
npm install          # first time only
npm run dev          # http://localhost:5173
```

API docs (Swagger UI): http://localhost:8000/docs

> Use `127.0.0.1`, not `localhost` — on Windows, `localhost` resolves to IPv6
> first and adds ~200 ms to every connection.

### Fill the database

```powershell
# Scrape + clean + match + load one category across all 15 retailers
python run_pipeline.py --category gpu

# Or sweep every category once
python scheduler.py --once
```

---

## Retailers (15)

StarTech · Ryans · Techland BD · PotakaIT · UCC · UltraTech · BinaryLogic ·
Skyland · Creatus · SellTech · ComputerSource · TrustTech · PCHouse · EZGadgets ·
VibeGaming

## Categories (24 live)

RAM Desktop · RAM Laptop · GPU · Processor · Motherboard · SSD · Portable SSD ·
HDD · Portable HDD · PSU · CPU Cooler · Casing Cooler · Casing · Monitor ·
Keyboard · Mouse · Headphone · UPS · Speaker · Webcam · Gaming Chair · Printer ·
Mouse Pad · Gamepad

> Prices are always in BDT (Bangladeshi Taka). All timestamps are UTC.
