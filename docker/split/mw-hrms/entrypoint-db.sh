#!/bin/bash
set -e
mkdir -p /var/run/mysqld && chown mysql:mysql /var/run/mysqld
if [ ! -d /var/lib/mysql/mysql ]; then
  mysql_install_db --user=mysql --datadir=/var/lib/mysql >/dev/null
fi
mysqld_safe --skip-networking=0 --bind-address=127.0.0.1 --datadir=/var/lib/mysql &
for i in $(seq 1 60); do mysqladmin -u root -phrms123456 ping --silent 2>/dev/null && break; sleep 2; done
DB_EXISTS=$(mysql -u root -phrms123456 -e "SHOW DATABASES LIKE '_041806a949bb7dd0'" 2>/dev/null | grep -c "_041806a949bb7dd0" || true)
if [ "$DB_EXISTS" -eq 0 ]; then
  mysql -u root -phrms123456 -e "CREATE DATABASE IF NOT EXISTS `_041806a949bb7dd0` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
  mysql -u root -phrms123456 _041806a949bb7dd0 < /mw-hrms-dump.sql
  mysql -u root -phrms123456 -e "CREATE USER IF NOT EXISTS '_041806a949bb7dd0'@'%' IDENTIFIED BY '1yMa70SeWYjkbmK9'; GRANT ALL PRIVILEGES ON `_041806a949bb7dd0`.* TO '_041806a949bb7dd0'@'%'; FLUSH PRIVILEGES;"
fi
wait
