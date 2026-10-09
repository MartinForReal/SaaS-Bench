#!/bin/sh
set -e
mkdir -p /var/lib/mysql
[ -d /var/lib/mysql/mysql ] || cp -a /opt/snapshot/mysql/. /var/lib/mysql/
exec mariadbd --user=mysql --datadir=/var/lib/mysql --bind-address=0.0.0.0 --port=3306 --skip-networking=0
