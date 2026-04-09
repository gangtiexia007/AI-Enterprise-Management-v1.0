#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker is not installed or not in PATH." >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "Error: neither 'docker compose' nor 'docker-compose' is available." >&2
  exit 1
fi

"${COMPOSE[@]}" down
"${COMPOSE[@]}" up -d --build
"${COMPOSE[@]}" ps

PRIMARY_IP=""
if PRIMARY_IP="$(hostname -I 2>/dev/null | awk '{print $1}')" && [[ -n "${PRIMARY_IP}" ]]; then
  :
elif command -v ipconfig >/dev/null 2>&1; then
  PRIMARY_IP="$(ipconfig getifaddr en0 2>/dev/null || true)"
  [[ -z "${PRIMARY_IP}" ]] && PRIMARY_IP="$(ipconfig getifaddr en1 2>/dev/null || true)"
fi
[[ -z "${PRIMARY_IP}" ]] && PRIMARY_IP="localhost"

echo "Deployment complete! Visit http://${PRIMARY_IP}"
