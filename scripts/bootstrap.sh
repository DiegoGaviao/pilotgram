#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

echo "==> Meta env from inventory"
python3 scripts/fill_meta_env.py

echo "==> Backend venv + pip"
cd "$ROOT/backend"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

echo "==> Web npm"
cd "$ROOT/web"
npm install --silent

echo "==> Done. Run: npm run dev (from $ROOT)"
