#!/bin/sh
set -e
until mariadb -h 127.0.0.1 -u root -e "SELECT 1" >/dev/null 2>&1; do sleep 1; done
exec /start.sh
