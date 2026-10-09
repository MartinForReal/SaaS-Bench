#!/bin/sh
set -e
exec mariadbd --user=mysql --datadir=/var/lib/mysql --bind-address=0.0.0.0
