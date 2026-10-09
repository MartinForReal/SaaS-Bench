#!/bin/sh
set -e
export AUTOMIGRATE=${AUTOMIGRATE:-yes}
exec /usr/local/bin/pretix webworker
