#!/bin/bash
# ═══════════════════════════════════════════════════════
#  Stock Portfolio Dashboard - Build & Run
#  Builds frontend, activates venv, runs backend
# ═══════════════════════════════════════════════════════

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/venv"

echo "╔══════════════════════════════════════════════╗"
echo "║  Stock Portfolio Dashboard - Build & Run     ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── Step 1: Build Frontend ──────────────────────────────
echo "── Frontend Build ──────────────────────────────────"

if ! command -v node &> /dev/null; then
    echo "Node.js not found. Please install Node.js to build the frontend."
    exit 1
fi

cd "$FRONTEND_DIR"

echo "Installing frontend dependencies..."
npm install --silent 2>/dev/null

echo "Building frontend (vite build)..."
npm run build

echo "Frontend built successfully -> frontend/dist/"
echo ""

# ── Step 2: Create & Activate Python Virtual Environment ─
echo "── Python Environment ──────────────────────────────"

if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required. Please install it first."
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment at backend/venv..."
    python3 -m venv "$VENV_DIR"
    echo "Virtual environment created."
else
    echo "Virtual environment already exists at backend/venv."
fi

echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

echo "Installing Python dependencies..."
pip install -r "$BACKEND_DIR/requirements.txt" --quiet

echo "Python environment ready ($(python3 --version))"
echo ""

# ── Step 3: Run Backend ─────────────────────────────────
echo "── Starting Backend ────────────────────────────────"
echo "   Backend:  http://127.0.0.1:8000"
echo "   API Docs: http://127.0.0.1:8000/docs"
echo ""
echo "   Frontend build served from: frontend/dist/"
echo "   Press Ctrl+C to stop the server."
echo ""

cd "$BACKEND_DIR"
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
