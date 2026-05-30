# DaamKoto — দাম কত?

**Compare PC component prices across Bangladesh's top retailers, in one place.**

DaamKoto lets Bangladeshi PC buyers search for any component (RAM, GPU, SSD, CPU…)
and instantly see its price compared across 13 local retailers — so you find the
cheapest source without tab-hopping. An AI chatbot layer lets you ask in plain
language ("find me 16GB DDR4 RAM under 4000 taka") and get real listings back.
The LLM understands; the database answers; the bot never invents prices.

Prices are stored append-only with timestamps, so you can also see how a part's
price changed over time.

---

## Architecture

| Stage | Folder | Tech |
|---|---|---|
| 1. Scrapers | `scrapers/` | Python + Playwright |
| 2. Clean & match | `cleaning/` | rapidfuzz |
| 3. Database | `database/` | PostgreSQL (append-only prices) |
| 4. Backend API | `backend/` | FastAPI + Uvicorn |
| 5. Frontend | `frontend-react/` | React 18 + Vite 6 + Tailwind CSS v4 |

The AI chatbot uses the Anthropic Claude API to translate natural language into
structured query parameters.

---

## Run locally

```bash
# 1. Activate the virtual environment (every new terminal)
.\venv\Scripts\Activate.ps1

# 2. Backend (Terminal 1)
python -m uvicorn backend.main:app --reload --port 8000

# 3. Frontend (Terminal 2)
cd frontend-react
npm install
npm run dev          # http://localhost:5173
```

API docs (Swagger UI): http://localhost:8000/docs

---

## Deployment

- **Frontend** deploys to **Vercel** (root directory: `frontend-react`).
  Set the env var `VITE_API_BASE` to your hosted backend URL.
- **Backend + PostgreSQL** must be hosted separately (e.g. Render or Railway +
  a managed Postgres instance) — Vercel only serves the static frontend.

See `frontend-react/.env.example` for the frontend env var.

---

## Retailers in scope (13)

StarTech · Ryans · Techland BD · PotakaIT · UCC · UltraTech · BinaryLogic ·
Skyland · Creatus · SellTech · ComputerSource · TrustTech · PCHouse

> Prices are always in BDT (Bangladeshi Taka). All timestamps are UTC.
