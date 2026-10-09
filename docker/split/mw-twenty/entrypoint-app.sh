#!/bin/sh
set -e
until pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; do sleep 1; done
until redis-cli -h 127.0.0.1 ping >/dev/null 2>&1; do sleep 1; done
export PG_DATABASE_URL="postgres://postgres:twenty_postgres_pass@127.0.0.1:5432/default"
export REDIS_URL="redis://127.0.0.1:6379"
export APP_SECRET="${APP_SECRET:-mw_twenty_secret_key_for_reset}"
export SERVER_URL="${SERVER_URL:-http://localhost:7039}"
export REACT_APP_SERVER_BASE_URL="${SERVER_URL}"
export NODE_PORT="3000"
exec /app/entrypoint.sh "$@"
