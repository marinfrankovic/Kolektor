#!/usr/bin/env bash
# Build and (re)start Kolektor on the current host.
#
#   ./deploy/deploy.sh            build and start
#   ./deploy/deploy.sh --no-build restart without rebuilding
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
    echo "No .env found. Copy .env.example to .env and fill it in first." >&2
    exit 1
fi

if [[ "$(stat -c %a .env)" != "600" ]]; then
    echo "Tightening permissions on .env"
    chmod 600 .env
fi

if [[ "${1:-}" == "--no-build" ]]; then
    docker compose up -d
else
    docker compose build
    docker compose up -d
fi

echo "Waiting for the app to report healthy…"
for _ in $(seq 1 60); do
    state="$(docker inspect -f '{{.State.Health.Status}}' kolektor-app 2>/dev/null || echo starting)"
    [[ "$state" == "healthy" ]] && break
    sleep 5
done

docker compose ps
port="$(grep -E '^KOLEKTOR_HTTP_PORT=' .env | cut -d= -f2 || true)"
echo "Kolektor is on http://$(hostname -I | awk '{print $1}'):${port:-8100}"
