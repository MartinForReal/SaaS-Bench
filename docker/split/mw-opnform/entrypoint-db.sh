#!/bin/sh
set -e
mkdir -p /var/lib/postgresql/data /run/postgresql
chown -R postgres:postgres /var/lib/postgresql/data /run/postgresql
[ -f /var/lib/postgresql/data/PG_VERSION ] || cp -a /opt/snapshot/pgdata/. /var/lib/postgresql/data/
PG_BIN=/usr/libexec/postgresql16; [ -d "$PG_BIN" ] || PG_BIN=/usr/bin
exec su - postgres -s /bin/bash -c "$PG_BIN/postgres -D /var/lib/postgresql/data -k /run/postgresql"
