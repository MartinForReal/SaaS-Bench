#!/bin/sh
set -e
PGDATA=${PGDATA:-/var/lib/postgresql/data}
mkdir -p "$PGDATA"
chown -R postgres:postgres "$PGDATA"
if [ ! -f "$PGDATA/PG_VERSION" ]; then
  su postgres -s /bin/bash -c "initdb -D $PGDATA"
  echo "host all all 127.0.0.1/32 trust" >> "$PGDATA/pg_hba.conf"
fi
exec su postgres -s /bin/bash -c "postgres -D $PGDATA"
