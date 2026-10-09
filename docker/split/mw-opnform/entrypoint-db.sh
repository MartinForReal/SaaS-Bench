#!/bin/sh
set -e
PG_BIN=/usr/libexec/postgresql16; [ -d "$PG_BIN" ] || PG_BIN=/usr/bin
exec su - postgres -s /bin/bash -c "$PG_BIN/postgres -D /var/lib/postgresql/data"
