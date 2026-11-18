#!/usr/bin/env bash
# One command: install Shield, create settings, start it, open the demo page. No Gmail needed (FakeMail).
#   bash demo/start.sh
set -euo pipefail
cd "$(dirname "$0")/../backend"

PY=python3
command -v $PY >/dev/null || { echo "Python 3 not found. On a Mac run: xcode-select --install  (then re-run this)"; exit 1; }

if [ ! -d .venv ]; then
  echo "→ Installing Shield (first run only, ~1 min)…"
  $PY -m venv .venv
  ./.venv/bin/pip install -q --upgrade pip
  ./.venv/bin/pip install -q -e ".[gmail,test]"
fi

if [ ! -f .env ]; then
  SECRET="shield-$(./.venv/bin/python -c 'import secrets;print(secrets.token_hex(5))')"
  cat > .env <<ENV
SHIELD_USER_SECRET=$SECRET
FOUNDER_NAME=Sneha
FOUNDER_TEST_GMAIL=sneha.demo@example.com
INVESTOR_TEST_GMAIL=priya@northbeam.example
SECOND_TEST_EMAIL=riya@acme.test
THIRD_TEST_EMAIL=ramesh@kirana.test
FOURTH_TEST_EMAIL=karan@angel.test
COFOUNDER_TEST_EMAIL=ananya@ownco.test
ACCOUNTANT_TEST_EMAIL=vikram@joshi.test
SHIELD_MAIL=fake
SHIELD_WATCH=off
SHIELD_ENABLE_DEV=0
ENV
fi
SECRET=$(grep '^SHIELD_USER_SECRET=' .env | cut -d= -f2-)

rm -rf runtime   # fresh demo state each start
echo
echo "════════════════════════════════════════════════════════"
echo "  Shield is starting."
echo "  Login password:  $SECRET"
echo "  Demo page:       http://127.0.0.1:8000/intake"
echo "  Stop with Ctrl+C. Run this script again for a fresh take."
echo "════════════════════════════════════════════════════════"
echo
( sleep 3; command -v open >/dev/null && open "http://127.0.0.1:8000/intake" ) &
exec ./.venv/bin/python -m app
