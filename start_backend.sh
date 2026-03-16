#!/bin/bash
# Start only the backend server
cd "$(dirname "$0")/backend"
echo "🚀 Starting backend at http://127.0.0.1:9999"
echo "   API Docs: http://127.0.0.1:9999/docs"
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 9999 --reload
