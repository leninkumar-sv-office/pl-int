#!/bin/bash
# ═══════════════════════════════════════════════════════
#  Stock Portfolio Dashboard - Startup Script
# ═══════════════════════════════════════════════════════

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

echo "╔══════════════════════════════════════════════╗"
echo "║    Stock Portfolio Dashboard                 ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── Check Python ──────────────────────────────────────
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required. Please install it first."
    exit 1
fi

# ── Install Python dependencies ───────────────────────
echo "📦 Installing Python dependencies..."
cd "$BACKEND_DIR"
pip3 install -r requirements.txt --quiet 2>/dev/null || pip install -r requirements.txt --quiet

# ── Check Node.js ─────────────────────────────────────
if command -v node &> /dev/null; then
    echo "📦 Installing frontend dependencies..."
    cd "$FRONTEND_DIR"
    npm install --silent 2>/dev/null

    echo ""
    echo "🚀 Starting services..."
    echo "   Backend:  http://127.0.0.1:9999"
    echo "   Frontend: http://localhost:5173"
    echo ""
    echo "   API Docs: http://127.0.0.1:9999/docs"
    echo ""

    # Start backend in background
    cd "$BACKEND_DIR"
    python3 -m uvicorn app.main:app --host 0.0.0.0 --port 9999 --reload &
    BACKEND_PID=$!

    # Start frontend
    cd "$FRONTEND_DIR"
    npm run dev &
    FRONTEND_PID=$!

    # Trap to kill both on exit
    trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT

    echo "Press Ctrl+C to stop both servers."
    wait
else
    echo ""
    echo "⚠️  Node.js not found. Starting backend only."
    echo "   Install Node.js to run the React frontend."
    echo ""
    echo "🚀 Starting backend at http://127.0.0.1:8000"
    echo "   API Docs: http://127.0.0.1:9999/docs"
    echo ""

    cd "$BACKEND_DIR"
    python3 -m uvicorn app.main:app --host 0.0.0.0 --port 9999 --reload
fi
