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

# The container runs as uid 10001, so a bind-mounted media directory has to be
# writable by that uid. Docker named volumes inherit the image owner already.
media_dir="$(grep -E '^KOLEKTOR_MEDIA_DIR=' .env | cut -d= -f2- || true)"
media_dir="${media_dir:-./data/media}"
mkdir -p "$media_dir"
if [[ "$(stat -c %u "$media_dir")" != "10001" ]]; then
    echo "Handing $media_dir to the container user (uid 10001)"
    chown -R 10001:10001 "$media_dir"
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
