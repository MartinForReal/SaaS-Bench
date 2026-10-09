#!/bin/sh
set -e
exec su-exec postgres postgres -D /var/lib/postgresql/data
