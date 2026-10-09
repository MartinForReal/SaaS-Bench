#!/bin/bash
set -e
export PRETIX_URL="${PRETIX_URL:-http://localhost:6089}"
until pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; do sleep 1; done
until redis-cli -h 127.0.0.1 ping >/dev/null 2>&1; do sleep 1; done
sed -i "s|^url=.*|url=${PRETIX_URL}|" /etc/pretix/pretix.cfg 2>/dev/null || true
exec /usr/local/bin/pretix "$@"
