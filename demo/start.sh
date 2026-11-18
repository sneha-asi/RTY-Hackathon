#!/usr/bin/env bash
# One command: install Shield, create settings, start it, open the demo page. No Gmail needed (FakeMail).
#   bash demo/start.sh
set -euo pipefail
cd "$(dirname "$0")/../backend"

# Find a working Python 3.11+ WITHOUT triggering Apple's Xcode installer (/usr/bin/python3 is only a stub
# unless the Command Line Tools are installed). If none is found, download a standalone Python with uv.
PY=""
for cand in /opt/homebrew/bin/python3 /usr/local/bin/python3 /Library/Frameworks/Python.framework/Versions/3.1*/bin/python3 "$HOME/.local/bin/python3"; do
  if [ -x "$cand" ] && "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then PY="$cand"; break; fi
done
if [ -z "$PY" ] && [ "$(uname)" != "Darwin" ] && command -v python3 >/dev/null && python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  PY="$(command -v python3)"
fi
if [ -z "$PY" ] && [ "$(uname)" = "Darwin" ] && xcode-select -p >/dev/null 2>&1 && /usr/bin/python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
  PY=/usr/bin/python3
fi

if [ ! -d .venv ]; then
  echo "→ Installing Shield (first run only, ~1-2 min)…"
  if [ -n "$PY" ]; then
    "$PY" -m venv .venv
  else
    echo "→ No usable Python found; downloading a standalone Python with uv (no Xcode needed)…"
    UV="$HOME/.local/bin/uv"
    [ -x "$UV" ] || curl -LsSf https://astral.sh/uv/install.sh | sh
    [ -x "$UV" ] || UV="$(command -v uv)"
    "$UV" venv --python 3.12 .venv
    "$UV" pip install --python .venv/bin/python -q pip
  fi
  ./.venv/bin/python -m pip install -q --upgrade pip
  ./.venv/bin/python -m pip install -q -e ".[gmail,test]"
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
