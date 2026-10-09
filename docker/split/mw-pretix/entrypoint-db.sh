#!/bin/sh
set -e
exec su postgres -s /bin/bash -c "postgres -D /var/lib/postgresql/data"
