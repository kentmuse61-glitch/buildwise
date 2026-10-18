#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [[ -f .env ]]; then
  set -a
  # Local-only configuration. Do not put secrets in Git.
  source .env
  set +a
fi

exec python -m uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}"
