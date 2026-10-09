#!/bin/bash
set -e
until pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; do sleep 1; done
until redis-cli -h 127.0.0.1 ping >/dev/null 2>&1; do sleep 1; done
php /usr/share/nginx/html/artisan migrate --force >/dev/null 2>&1 || true
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/opnform-app.conf
