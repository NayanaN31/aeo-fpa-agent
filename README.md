# AEO FP&A Agent

AI-powered Financial Planning & Analysis copilot for American Eagle Outfitters, built on real SEC 10-K filings.

![Dashboard](https://img.shields.io/badge/stack-React%20%2B%20FastAPI%20%2B%20GPT--4o-blue)

## What It Does

- **Revenue Forecasting** — Component P&L model (4.1% MAPE on backtests)
- **Scenario Modeling** — "What if comp sales decline 3%?" with full P&L impact
- **Causal Analysis** — Margin bridge decomposing OI changes into volume, cost, and leverage drivers
- **Competitor Benchmarking** — AEO vs ANF, URBN, LULU, VSCO, BKE, Gap
- **Quarterly Trends** — Drill into intra-year seasonality and margin shifts
- **Proactive Insights** — Key signals surfaced on load, no prompting required

## Quick Start

### Prerequisites

- **Python 3.10+** — [python.org](https://python.org)
- **Node.js 18+** — [nodejs.org](https://nodejs.org)
- **OpenAI API key** — [platform.openai.com](https://platform.openai.com/api-keys)

### Setup (one-time)

```bash
# 1. Clone or download this folder
cd aeo_fpa_agent

# 2. Create your .env file with your OpenAI API key
echo 'OPENAI_API_KEY=sk-your-key-here' > .env

# 3. Run the startup script (installs deps + starts servers)
./start.sh
```

That's it. Open **http://localhost:5173** in your browser.

### Manual Setup (if start.sh doesn't work)

```bash
# Install Python dependencies
pip3 install -r requirements.txt

# Install Node dependencies
npm install

# Start the API server (terminal 1)
python3 src/04_api_server.py

# Start the dashboard (terminal 2)
npm run dev
```

Open **http://localhost:5173**.

## Project Structure

```
aeo_fpa_agent/
├── src/
│   ├── 01_fetch_filings.py      # Download 10-K filings from SEC EDGAR
│   ├── 02_extract_financials.py  # Parse iXBRL → structured JSON
│   ├── 03_build_agent.py        # FP&A agent + forecast model + eval
│   ├── 04_api_server.py         # FastAPI backend for the dashboard
│   ├── 05_competitors.py        # Fetch peer company data
│   ├── 06_extract_segments.py   # AE brand vs Aerie brand breakdown
│   ├── 07_fetch_quarterly.py    # Quarterly data from XBRL API
│   ├── dashboard.jsx            # React single-page dashboard
│   ├── main.jsx                 # React entry point
│   └── index.css                # Tailwind base styles
├── data/
│   ├── raw/                     # Downloaded 10-K HTML files
│   └── processed/               # Extracted JSON (financials, segments, peers)
├── eval/
│   └── backtest_results.json    # Forecast accuracy metrics
├── .env                         # Your OpenAI API key (not committed)
├── requirements.txt             # Python dependencies
├── package.json                 # Node dependencies
├── start.sh                     # One-command setup & launch
└── README.md
```

## Key Demo Flows

1. **Executive Briefing** — Loads automatically with 3-sentence AI summary + key signals
2. **Forecast** — Click "FY2025 forecast: $X,XXXM revenue — stress test it"
3. **Causal Analysis** — "Why did OI jump 92% in FY2024?" → margin bridge decomposition
4. **Scenario** — "What if comp sales decline 5%?" → full P&L impact
5. **Competitors** — Switch to Competitors tab for peer margin benchmarks
6. **Quarterly** — "Show me quarterly trends for FY2024"

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI Model | GPT-4o via OpenAI API (native function calling) |
| Backend | FastAPI + uvicorn |
| Frontend | React 18 + Recharts + Tailwind CSS |
| Build | Vite |
| Data Source | SEC EDGAR (10-K filings, XBRL API) |

## GitHub Pages (public `github.io` demo)

Push to GitHub, enable **Settings → Pages → GitHub Actions**, and the workflow publishes a static build to `https://<you>.github.io/<repo>/`. Charts and briefing work from embedded data; live chat needs the API (local or hosted). Full steps: [docs/DEPLOY_GITHUB_PAGES.md](docs/DEPLOY_GITHUB_PAGES.md).

## Troubleshooting

**"Cannot reach the API server"** — Make sure `python3 src/04_api_server.py` is running on port 8000.

**"ModuleNotFoundError: No module named 'openai'"** — Run `pip3 install -r requirements.txt`.

**Port already in use** — Kill existing processes: `kill $(lsof -ti:8000) $(lsof -ti:5173) 2>/dev/null`

**Data files missing** — Run the pipeline manually:
```bash
python3 src/01_fetch_filings.py
python3 src/02_extract_financials.py
python3 src/05_competitors.py
python3 src/06_extract_segments.py
python3 src/07_fetch_quarterly.py
```
