#!/bin/bash
# Start only the frontend dev server
cd "$(dirname "$0")/frontend"
echo "🚀 Starting frontend at http://localhost:5173"
npm run dev
