#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# ── Colors ────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   AEO FP&A Agent — Setup & Launch            ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ── Check prerequisites ──────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}Error: python3 is not installed.${NC}"
    echo "Install Python 3.10+ from https://python.org"
    exit 1
fi

if ! command -v node &>/dev/null; then
    echo -e "${RED}Error: node is not installed.${NC}"
    echo "Install Node.js 18+ from https://nodejs.org"
    exit 1
fi

# ── API key (optional for UI; required for full AI chat / GPT summary) ───────
if [ ! -f .env ] || ! grep -qE '^[[:space:]]*OPENAI_API_KEY=[^[:space:]]+' .env 2>/dev/null; then
    echo -e "${RED}Note:${NC} No OPENAI_API_KEY in .env — dashboard and charts still run;"
    echo "      add your key to .env for GPT-powered chat and the AI executive briefing."
    echo ""
fi

# ── Install Python dependencies ──────────────────────────────────────────────
echo -e "${GREEN}[1/4]${NC} Installing Python dependencies..."
pip3 install -q -r requirements.txt 2>/dev/null || python3 -m pip install -q -r requirements.txt

# ── Install Node dependencies ────────────────────────────────────────────────
echo -e "${GREEN}[2/4]${NC} Installing Node dependencies..."
if [ ! -d node_modules ]; then
    npm install --silent
else
    echo "  node_modules/ exists, skipping. Run 'npm install' to update."
fi

# ── Check if processed data exists, if not run the pipeline ──────────────────
echo -e "${GREEN}[3/4]${NC} Checking data files..."
if [ ! -f data/processed/aeo_financials.json ]; then
    echo "  Fetching and processing SEC filings (first run only, ~2 minutes)..."
    python3 src/01_fetch_filings.py
    python3 src/02_extract_financials.py
    python3 src/05_competitors.py
    python3 src/06_extract_segments.py
    python3 src/07_fetch_quarterly.py
    echo -e "  ${GREEN}Data pipeline complete.${NC}"
else
    echo "  Processed data found. Skipping pipeline."
fi

# ── Start servers ────────────────────────────────────────────────────────────
echo -e "${GREEN}[4/4]${NC} Starting servers..."

# Kill any existing processes on our ports
kill $(lsof -ti:8000) 2>/dev/null || true
kill $(lsof -ti:5173) 2>/dev/null || true
sleep 1

# Start API server in background
echo "  Starting API server on http://localhost:8000 ..."
python3 src/04_api_server.py &
API_PID=$!

# Start Vite dev server in background
echo "  Starting dashboard on http://localhost:5173 ..."
npm run dev &
VITE_PID=$!

sleep 3

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Ready! Open http://localhost:5173           ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "  API server:  http://localhost:8000  (PID $API_PID)"
echo "  Dashboard:   http://localhost:5173  (PID $VITE_PID)"
echo ""
echo "  To share with others, run in a new terminal:"
echo "    ngrok http 5173"
echo ""
echo "  Press Ctrl+C to stop both servers."

# Wait for either process to exit, then clean up
trap "kill $API_PID $VITE_PID 2>/dev/null; exit 0" SIGINT SIGTERM
wait
