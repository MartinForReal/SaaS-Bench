#!/bin/sh
set -e
until nc -z 127.0.0.1 3306; do sleep 1; done
exec /start.sh
