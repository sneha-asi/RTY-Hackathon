#!/usr/bin/env bash
# Reset Shield's sandbox (actions, ledger, journal, runtime file copies) between rehearsals.
set -euo pipefail
curl -fsS -X POST http://127.0.0.1:${SHIELD_OWNER_PORT:-8000}/dev/reset >/dev/null
echo "Shield reset. Owner console: http://127.0.0.1:${SHIELD_OWNER_PORT:-8000}  ·  MCP: http://127.0.0.1:${SHIELD_MCP_PORT:-8765}/mcp"
