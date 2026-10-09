#!/bin/sh
set -e
mkdir -p /run/mysqld && chown -R mysql:mysql /run/mysqld
if [ ! -d /var/lib/mysql/mysql ]; then
  mariadb-install-db --user=mysql --datadir=/var/lib/mysql >/dev/null
fi
exec mariadbd --user=mysql --datadir=/var/lib/mysql --bind-address=0.0.0.0
