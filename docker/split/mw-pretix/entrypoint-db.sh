#!/bin/sh
set -e
mkdir -p /var/lib/postgresql/data /run/postgresql
chown -R postgres:postgres /var/lib/postgresql/data /run/postgresql
[ -f /var/lib/postgresql/data/PG_VERSION ] || cp -a /opt/snapshot/pgdata/. /var/lib/postgresql/data/
exec su postgres -s /bin/bash -c "postgres -D /var/lib/postgresql/data -k /run/postgresql"
