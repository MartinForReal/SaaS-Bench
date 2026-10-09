#!/bin/sh
set -e
exec redis-server --bind 0.0.0.0 --port 6379
