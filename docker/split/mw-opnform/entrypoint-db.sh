#!/bin/bash
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
