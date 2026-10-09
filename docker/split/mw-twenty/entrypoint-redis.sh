#!/bin/sh
set -e
exec redis-server /etc/redis.conf --bind 127.0.0.1 --port 6379
