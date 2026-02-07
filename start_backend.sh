#!/bin/bash
# Start only the backend server
cd "$(dirname "$0")/backend"
echo "🚀 Starting backend at http://127.0.0.1:8000"
echo "   API Docs: http://127.0.0.1:8000/docs"
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
