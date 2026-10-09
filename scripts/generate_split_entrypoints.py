"""Write real per-service entrypoints + Dockerfiles for the sidecar split.

Derived from the images real entrypoints (mw-entrypoint.sh / start.sh /
entrypoint-mw.sh / entrypoint.sh) so each container runs exactly one service and
the app container still runs the fixture / migrations before serving.
"""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docker" / "split"

APPS: dict[str, dict[str, str]] = {}

APPS["mw-twenty"] = {
    "db": """#!/bin/sh
set -e
PGDATA=${PGDATA:-/var/lib/postgresql/data}
mkdir -p "$PGDATA"
chown -R postgres:postgres "$PGDATA"
if [ ! -f "$PGDATA/PG_VERSION" ]; then
  su-exec postgres initdb -D "$PGDATA"
  echo "host all all 127.0.0.1/32 trust" >> "$PGDATA/pg_hba.conf"
  echo "listen_addresses = '127.0.0.1'" >> "$PGDATA/postgresql.conf"
fi
exec su-exec postgres postgres -D "$PGDATA"
""",
    "redis": """#!/bin/sh
set -e
exec redis-server /etc/redis.conf --bind 127.0.0.1 --port 6379
""",
    "app": """#!/bin/sh
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
""",
}

APPS["mw-hrms"] = {
    "db": """#!/bin/bash
set -e
mkdir -p /var/run/mysqld && chown mysql:mysql /var/run/mysqld
if [ ! -d /var/lib/mysql/mysql ]; then
  mysql_install_db --user=mysql --datadir=/var/lib/mysql >/dev/null
fi
mysqld_safe --skip-networking=0 --bind-address=127.0.0.1 --datadir=/var/lib/mysql &
for i in $(seq 1 60); do mysqladmin -u root -phrms123456 ping --silent 2>/dev/null && break; sleep 2; done
DB_EXISTS=$(mysql -u root -phrms123456 -e "SHOW DATABASES LIKE '_041806a949bb7dd0'" 2>/dev/null | grep -c "_041806a949bb7dd0" || true)
if [ "$DB_EXISTS" -eq 0 ]; then
  mysql -u root -phrms123456 -e "CREATE DATABASE IF NOT EXISTS `_041806a949bb7dd0` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
  mysql -u root -phrms123456 _041806a949bb7dd0 < /mw-hrms-dump.sql
  mysql -u root -phrms123456 -e "CREATE USER IF NOT EXISTS '_041806a949bb7dd0'@'%' IDENTIFIED BY '1yMa70SeWYjkbmK9'; GRANT ALL PRIVILEGES ON `_041806a949bb7dd0`.* TO '_041806a949bb7dd0'@'%'; FLUSH PRIVILEGES;"
fi
wait
""",
    "redis": """#!/bin/sh
set -e
exec redis-server --bind 0.0.0.0 --port 6379
""",
    "app": """#!/bin/bash
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
""",
}

APPS["mw-booklore"] = {
    "db": """#!/bin/sh
set -e
mkdir -p /run/mysqld && chown -R mysql:mysql /run/mysqld
if [ ! -d /var/lib/mysql/mysql ]; then
  mariadb-install-db --user=mysql --datadir=/var/lib/mysql >/dev/null
fi
exec mariadbd --user=mysql --datadir=/var/lib/mysql --bind-address=0.0.0.0
""",
    "app": """#!/bin/sh
set -e
until mariadb -h 127.0.0.1 -u root -e "SELECT 1" >/dev/null 2>&1; do sleep 1; done
exec /start.sh
""",
}

APPS["mw-pretix"] = {
    "db": """#!/bin/sh
set -e
PGDATA=${PGDATA:-/var/lib/postgresql/data}
mkdir -p "$PGDATA"
chown -R postgres:postgres "$PGDATA"
if [ ! -f "$PGDATA/PG_VERSION" ]; then
  su postgres -s /bin/bash -c "initdb -D $PGDATA"
  echo "host all all 127.0.0.1/32 trust" >> "$PGDATA/pg_hba.conf"
fi
exec su postgres -s /bin/bash -c "postgres -D $PGDATA"
""",
    "redis": """#!/bin/sh
set -e
exec redis-server --bind 0.0.0.0 --port 6379
""",
    "app": """#!/bin/bash
set -e
export PRETIX_URL="${PRETIX_URL:-http://localhost:6089}"
until pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; do sleep 1; done
until redis-cli -h 127.0.0.1 ping >/dev/null 2>&1; do sleep 1; done
sed -i "s|^url=.*|url=${PRETIX_URL}|" /etc/pretix/pretix.cfg 2>/dev/null || true
exec /usr/local/bin/pretix "$@"
""",
}

APPS["mw-opnform"] = {
    "db": """#!/bin/bash
set -e
PG_BIN=/usr/libexec/postgresql16
[ -d "$PG_BIN" ] || PG_BIN=/usr/bin
PGDATA=${PGDATA:-/var/lib/postgresql/data}
mkdir -p "$PGDATA" /run/postgresql
id postgres >/dev/null 2>&1 || adduser -D -h /var/lib/postgresql postgres
chown -R postgres:postgres "$PGDATA" /run/postgresql
if [ ! -f "$PGDATA/PG_VERSION" ]; then
  su - postgres -s /bin/bash -c "$PG_BIN/initdb -D $PGDATA"
  echo "host all all 0.0.0.0/0 trust" >> "$PGDATA/pg_hba.conf"
  echo "listen_addresses = '*'" >> "$PGDATA/postgresql.conf"
fi
exec su - postgres -s /bin/bash -c "$PG_BIN/postgres -D $PGDATA"
""",
    "redis": """#!/bin/sh
set -e
exec redis-server --bind 0.0.0.0 --port 6379
""",
    "app": """#!/bin/bash
set -e
until pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; do sleep 1; done
until redis-cli -h 127.0.0.1 ping >/dev/null 2>&1; do sleep 1; done
php /usr/share/nginx/html/artisan migrate --force >/dev/null 2>&1 || true
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/opnform-app.conf
""",
}

TEMPLATE = """# syntax=docker/dockerfile:1.7
#
# Split image: ONE service per container ({service}).
#
# Base bundle : {image}
# Entrypoint  : added by this image (entrypoint-{service}.sh)
#
# The app container still runs the fixture / migrations before serving; the db and
# redis containers only initialise their datadir (if empty) and then serve.

ARG BASE_IMAGE={image}:latest
FROM ${{BASE_IMAGE}}

USER root
COPY entrypoint-{service}.sh /opt/saas-bench/entrypoint-{service}.sh
RUN chmod +x /opt/saas-bench/entrypoint-{service}.sh
ENTRYPOINT ["/opt/saas-bench/entrypoint-{service}.sh"]
"""


def main() -> None:
    written = 0
    for image, services in APPS.items():
        for service, script in services.items():
            path = OUT / image / f"entrypoint-{service}.sh"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(script, encoding="utf-8", newline="\n")
            dockerfile = OUT / image / f"Dockerfile.{service}"
            dockerfile.write_text(
                TEMPLATE.format(image=image, service=service), encoding="utf-8", newline="\n"
            )
            written += 1
    print(f"wrote {written} entrypoints + Dockerfiles")


if __name__ == "__main__":
    main()