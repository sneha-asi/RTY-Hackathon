#!/usr/bin/env bash
# Reset Shield's sandbox (actions, ledger, journal, runtime file copies) between rehearsals.
# Usage: SHIELD_USER_SECRET=... demo/scripts/demo_reset.sh   (reads backend/.env if the variable is unset)
set -euo pipefail
here="$(cd "$(dirname "$0")/../../backend" && pwd)"
if [ -z "${SHIELD_USER_SECRET:-}" ] && [ -f "$here/.env" ]; then
  SHIELD_USER_SECRET="$(grep -E '^SHIELD_USER_SECRET=' "$here/.env" | cut -d= -f2- | cut -d' ' -f1)"
fi
port="${SHIELD_OWNER_PORT:-8000}"
curl -fsS -X POST -H "X-Shield-Secret: ${SHIELD_USER_SECRET:?set SHIELD_USER_SECRET}" "http://127.0.0.1:$port/dev/reset" >/dev/null
echo "Shield reset. Owner console: http://127.0.0.1:$port  ·  MCP: http://127.0.0.1:${SHIELD_MCP_PORT:-8765}/mcp"
