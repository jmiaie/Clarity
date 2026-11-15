#!/bin/bash
# Run Clarity locally: API on http://localhost:8000, app on http://localhost:5173
set -e
cd "$(dirname "$0")"

if [ ! -d backend/venv ]; then
  python3 -m venv backend/venv
  backend/venv/bin/pip install -r backend/requirements-dev.txt
fi
if [ ! -d frontend/node_modules ]; then
  (cd frontend && npm install)
fi

(cd backend && venv/bin/uvicorn app.main:app --reload --port 8000) &
API_PID=$!
trap 'kill $API_PID 2>/dev/null' EXIT
(cd frontend && npm run dev)
