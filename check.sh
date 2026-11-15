#!/bin/bash
# Run every automated check: backend tests (including the HTTP + database tests) and the frontend production build.
set -e
cd "$(dirname "$0")"

if [ ! -d backend/venv ]; then
  python3 -m venv backend/venv
fi
backend/venv/bin/pip install -q -r backend/requirements-dev.txt
(cd backend && venv/bin/pytest -q)

(cd frontend && npm install --silent && npm run build)
echo "All checks passed."
