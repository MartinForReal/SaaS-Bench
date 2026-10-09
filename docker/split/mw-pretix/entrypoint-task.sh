#!/bin/sh
set -e
export AUTOMIGRATE=skip
exec /usr/local/bin/pretix taskworker
