#!/bin/bash
set -e
export HOME=/home/frappe
export PATH="/home/frappe/.local/bin:/home/frappe/frappe-bench/env/bin:$PATH"
export PYTHONPATH="/home/frappe/frappe-bench/env/lib/python3.14/site-packages"
until mysqladmin -h 127.0.0.1 -u root -phrms123456 ping --silent 2>/dev/null; do sleep 2; done
until redis-cli -h 127.0.0.1 ping >/dev/null 2>&1; do sleep 1; done
exec su -s /bin/bash frappe -c "
export PATH='/home/frappe/.local/bin:/home/frappe/frappe-bench/env/bin:/usr/bin:/usr/local/bin:$PATH'
export GIT_PYTHON_GIT_EXECUTABLE=/usr/bin/git
cd /home/frappe/frappe-bench
bench set-mariadb-host 127.0.0.1 || true
bench set-redis-cache-host redis://127.0.0.1:6379 || true
bench set-redis-queue-host redis://127.0.0.1:6379 || true
bench set-redis-socketio-host redis://127.0.0.1:6379 || true
sed -i '/redis/d' ./Procfile || true
sed -i '/watch/d' ./Procfile || true
bench --site hrms.localhost clear-cache || true
exec bench start"
