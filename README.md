# 🏢 AgentCompany

> An AI-powered virtual startup simulator. Give it an industry, and a team of 13 specialised AI agents will research the market, design a product, stress-test the finances, and decide whether to build — all in under 10 minutes.

**CEO:** You | **AI Backend:** DeepSeek API | **Average run cost:** $0.01–$0.05

---

## What It Does

AgentCompany runs a full startup pipeline autonomously:

1. **Scans the web** for real competitor news and market trends (DuckDuckGo, no API key needed)
2. **Researches real user pain points** from reviews, forums, and complaints
3. **Designs an MVP product** with features, pricing, and customer segmentation
4. **Models the financials** — TAM, gross margin, CAC, payback period, ROI
5. **Gates the idea** with a composite score — passes or kills it before any engineering starts
6. **Architects + builds** the technical system if the idea passes (specs, backend code, frontend, QA)
7. **Launches** with a go-to-market strategy, outreach campaign, and infrastructure plan
8. **Reports** everything — CEO daily report, Notion sync, project folder with real code

Every run also **updates each agent's permanent knowledge graph** so they get smarter over time.

---

## The 13 AI Employees

| Agent | Role | Chamber |
|-------|------|---------|
| 🔍 **SENTRY** | Competitive Intelligence — real-time web search for threats | Sentinel |
| 👁️ **ARIA** | Market Research — finds the real user pain point | Chamber 1 |
| 💡 **NOVA** | Product Strategy — designs the MVP | Chamber 1 |
| 📊 **QUANT** | Financial Intelligence — TAM, margins, unit economics | Chamber 1 |
| 🛑 **GATE** | Chief Risk Officer — PASS or KILL (threshold: 6.0/10) | Chamber 1 |
| 💼 **LEDGER** | CFO — daily finance report + real API token cost tracking | Chamber 1 |
| ⚙️ **ARCH** | Systems Architect — technical blueprint | Chamber 2 |
| 🖥️ **PIXEL** | Frontend Engineer — UI specification | Chamber 2 |
| 🔧 **CORE** | Backend Engineer — generates real Python/FastAPI code | Chamber 2 |
| 🛡️ **VIGIL** | QA & Security — test plan + vulnerability scan | Chamber 2 |
| 🚀 **APEX** | Growth & Acquisition — go-to-market strategy | Chamber 3 |
| 🤝 **HAVEN** | Customer Success — onboarding & retention | Chamber 3 |
| 🏗️ **ORCA-1** | Infrastructure — deployment + cloud cost estimate | Chamber 3 |

Plus **5 Kaggle DataScience agents**: SCOUT, DARWIN, FORGE, OPTIMUS, HELM — for running ML competitions.

---

## Installation

### Prerequisites

- **Python 3.12+** — download from [python.org](https://www.python.org/downloads/)
- **Git** — download from [git-scm.com](https://git-scm.com/)
- **DeepSeek API key** — get one free at [platform.deepseek.com](https://platform.deepseek.com)

### Step 1 — Clone the repository

```bash
git clone https://github.com/your-org/AgentCompany.git
cd AgentCompany\AgentCompany
```

Or if you already have the folder, just open a terminal in `E:\AgentCompany\AgentCompany`.

### Step 2 — Create and activate the virtual environment

```bash
# Create venv
python -m venv venv

# Activate (Windows CMD)
venv\Scripts\activate

# Activate (Windows PowerShell)
venv\Scripts\Activate.ps1
```

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Set up your API keys

Create a `.env` file in the project root (`E:\AgentCompany\AgentCompany\.env`):

```env
# Required
DEEPSEEK_KEY=sk-your-deepseek-api-key-here

# Optional — for Notion logging
NOTION_API_KEY=secret_your-notion-integration-token
NOTION_PAGE_ID=your-notion-team-directory-page-id

# Optional — for Kaggle competitions
KAGGLE_CONFIG_DIR=E:\AgentCompany\AgentCompany
KAGGLE_USERNAME=your_kaggle_username
```

> **Get a DeepSeek API key:** Go to [platform.deepseek.com](https://platform.deepseek.com) → Sign up → API Keys → Create key.  
> Cost: ~$0.01–$0.05 per company run.

### Step 5 — (Optional) Set up the company dev environment

The `compvenv` is a separate Python environment used by agents to execute data science code:

```bash
python -m venv compvenv
compvenv\Scripts\pip install pandas numpy scikit-learn lightgbm xgboost optuna kaggle ddgs requests
```

### Step 6 — (Optional) Start FalkorDB for graph memory

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/). Skip this if you want SQLite fallback (works automatically without Docker).

```bash
# Double-click setup_falkordb.bat
# Or run manually:
docker-compose up -d
```

FalkorDB browser UI will be available at `http://localhost:3000`.

---

## Quick Start

### 1. Start the Server

Double-click `start_windows.bat` — opens a visible CMD window with live server logs.

Or manually:
```bash
cd E:\AgentCompany\AgentCompany
venv\Scripts\python.exe -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Open the Dashboard

```
http://localhost:8000
```

### 3. Run the Company

Type an industry in the top-right input and click **▶ Run Company**.

Or via API:
```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"industry": "B2B SaaS developer tools", "ad_budget_usd": 500}'
```

---

## CEO Dashboard Features

The web dashboard at `http://localhost:8000` has **6 tabs**:

| Tab | What It Shows |
|-----|---------------|
| 📊 **Dashboard** | Live agent activity feed, chamber progress, financial KPIs, CEO action items |
| 📋 **History** | All past runs — click any to expand gate scores, financials, tokens used |
| 📈 **Analytics** | Pass rate, total spend, avg cost/run, industries tried (bar chart + donut) |
| ⚙️ **Settings** | Change GATE threshold, budgets, agent models — no code editing needed |
| 🧠 **Memory** | Browse each agent's knowledge graph (nodes, edges, graph view) |
| 🏆 **Kaggle** | Run ML competitions — SCOUT picks one, agents write + execute real ML code |

### CEO Chat Bar

Type any message at the bottom of the dashboard:

```
@ARIA find the best niche in fintech for seniors
@QUANT re-model at $30/user with 70% gross margin target
Run an analysis on electric vehicle fleet software
Analyse the mental health app market
```

---

## Output: What Gets Generated

After every run, files are written automatically:

```
reports/
  {product_name}_report.md     ← Full AgentCompany analysis:
                                   gate scores, financials, competitive intel,
                                   smoke test results, CEO action items

projects/{product_name}/
  README.md                    ← How to run/use the product
  specs/technical_plan.md      ← ARCH: tech stack, DB schema, API routes
  src/backend/CODE/main.py     ← CORE: real Python/FastAPI code (~18KB)
  src/backend/CODE/database.py ← CORE: SQLAlchemy models
  src/frontend/build_manifest.md ← PIXEL: frontend spec
  tests/qa_report.md           ← VIGIL: QA results, P0/P1 bugs found
  marketing/outreach_campaign.md ← APEX: ICP, prospects, email template

logs/
  ceo_reports/YYYY-MM-DD.md    ← CEO daily report
  chamber1/YYYY-MM-DD.md       ← Full agent conversation logs
  ...
```

Notion is also updated automatically after every run (configurable in Settings).

---

## Agent Memory System

Every agent has **two layers of memory**:

### Long-Term Memory (Permanent — FalkorDB / SQLite)
- Stored in `data/memory/{AGENT_NAME}.db`
- Persists forever across sessions and restarts
- Stores: industries tried, pain points found, competitors, products designed, GATE scores, win/loss patterns
- Automatically injected into agent prompts on future runs for the same industry

### Short-Term Memory (Vector — per run)
- Created fresh at the start of each run, cleared after
- Uses `fastembed` (local ONNX embeddings, no GPU needed)
- All agents share the store — GATE can recall ARIA's pain points, NOVA can recall SENTRY's threats
- Semantically searched: agents query for relevant context, not just raw history

### Upgrade to FalkorDB (Optional)
```bash
# Requires Docker
docker-compose up -d
# Browser UI at http://localhost:3000
```
Without Docker, memory automatically falls back to SQLite.

---

## Kaggle DataScience Chamber

Run ML competitions autonomously:

```bash
# From the dashboard → Kaggle tab → enter competition slug → click Run Kaggle
# Or via API:
curl -X POST http://localhost:8000/kaggle/run \
  -d '{"competition_slug": "titanic", "target_type": "tabular"}'
```

The pipeline: **SCOUT** downloads data → **DARWIN** runs EDA (real Python execution) → **FORGE** writes LightGBM pipeline → **OPTIMUS** runs 40-trial Optuna HPO + ensemble → **HELM** submits to Kaggle leaderboard.

**Kaggle setup:**  
1. Go to [kaggle.com/settings](https://www.kaggle.com/settings) → API → **Create New Token** → downloads `kaggle.json`  
2. Place `kaggle.json` in `E:\AgentCompany\AgentCompany\kaggle.json`  
3. Add `KAGGLE_CONFIG_DIR=E:\AgentCompany\AgentCompany` to your `.env`

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | CEO Dashboard |
| `/run` | POST | Start a company run |
| `/chat` | POST | CEO message / agent directive |
| `/status` | GET | Current run status + result |
| `/events` | GET | SSE stream (real-time feed) |
| `/history` | GET | All past runs |
| `/analytics` | GET | Stats: pass rate, cost, industries |
| `/settings` | GET/POST | Read or update settings |
| `/memory` | GET | All agent memory stats |
| `/memory/{agent}` | GET | Full knowledge graph for one agent |
| `/kaggle/run` | POST | Start a Kaggle competition run |
| `/kaggle/status` | GET | Kaggle run status + results |

---

## Configuration

All settings are in two files:

**`config.py`** — non-secret settings (model assignments, temperatures, GATE threshold)

**`.env`** — API keys (never commit this):
```env
DEEPSEEK_KEY=sk-...
NOTION_API_KEY=secret_...
NOTION_PAGE_ID=<your-team-directory-page-id>
KAGGLE_CONFIG_DIR=E:\AgentCompany\AgentCompany
KAGGLE_USERNAME=your_kaggle_username
```

Settings can also be changed live from the ⚙️ Settings tab in the dashboard without editing any files.

---

## Project Structure

```
AgentCompany/
├── agents/
│   ├── base.py              ← BaseAgent (LLM calls, memory, context compression)
│   ├── sentinel.py          ← SENTRY (web search + competitor analysis)
│   ├── ledger.py            ← LEDGER (CFO, token cost tracking)
│   ├── chamber1/            ← ARIA, NOVA, QUANT, GATE
│   ├── chamber2/            ← ARCH, PIXEL, CORE, VIGIL
│   ├── chamber3/            ← APEX, HAVEN
│   └── kaggle/              ← SCOUT, DARWIN, FORGE, OPTIMUS, HELM
├── api/
│   └── server.py            ← FastAPI server, all endpoints, SSE stream
├── chambers/
│   └── kaggle/              ← KaggleChamber orchestrator
├── utils/
│   ├── agent_memory.py      ← Long-term graph memory (FalkorDB / SQLite)
│   ├── short_term_memory.py ← Per-run vector memory (fastembed)
│   ├── context_manager.py   ← Auto-compression for 128k context window
│   ├── web_search.py        ← DuckDuckGo search (no API key)
│   ├── code_executor.py     ← Safe Python execution in compvenv
│   ├── token_tracker.py     ← Real DeepSeek API token cost tracking
│   ├── history_logger.py    ← Saves every run to data/history.json
│   └── settings_manager.py  ← UI-editable settings (data/settings.json)
├── frontend/
│   └── dashboard.html       ← Full CEO Dashboard (6 tabs, live SSE)
├── models/
│   └── schemas.py           ← All Pydantic data models
├── orchestrator.py          ← Main pipeline orchestrator (ORCA-1)
├── data/
│   ├── memory/              ← Agent knowledge graphs (*.db files)
│   ├── kaggle/              ← Downloaded competition datasets
│   ├── history.json         ← All past run records
│   └── settings.json        ← Live settings
├── projects/                ← Generated project folders (code + specs)
├── reports/                 ← AgentCompany analysis reports
├── logs/                    ← Daily agent logs + CEO reports
├── compvenv/                ← Company dev environment (pandas, sklearn, lgb, etc.)
├── venv/                    ← Server runtime environment
├── docker-compose.yml       ← FalkorDB graph database (optional)
├── setup_falkordb.bat       ← One-click FalkorDB setup
└── start_windows.bat        ← One-click server start
```

---

## Troubleshooting

**Port 8000 in use** — `start_windows.bat` handles this automatically.

**GATE always kills** — Try a narrower niche. Adjust GATE threshold in Settings tab.

**No events in dashboard** — Hard refresh (Ctrl+Shift+R), then click Run Company fresh.

**Notion pages missing** — Check `NOTION_API_KEY` and `NOTION_PAGE_ID` in `.env`.

**Search errors** — DuckDuckGo rate limits occasionally. Agents fall back to LLM knowledge automatically.

---

## Requirements

| Requirement | Required? | Notes |
|-------------|-----------|-------|
| Python 3.12+ | ✅ Required | [python.org](https://www.python.org/downloads/) |
| DeepSeek API key | ✅ Required | [platform.deepseek.com](https://platform.deepseek.com) — ~$0.05/run |
| Notion integration | ⬜ Optional | For auto-posting reports to Notion |
| Kaggle API key | ⬜ Optional | For the Kaggle DataScience chamber |
| Docker Desktop | ⬜ Optional | For FalkorDB graph memory (SQLite fallback works without it) |
| 2GB+ disk space | ✅ Required | For venv, compvenv, and downloaded datasets |

---

*Built with DeepSeek AI · CEO: You*
