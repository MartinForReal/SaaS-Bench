"""Snapshot (pre-warmed datadir) DB images for the sidecar split.

Each image runs the apps own init/migrate/seed step once at build time, stops the
database cleanly, and copies the datadir into a scratch runtime image. The pod then
serves the already-migrated datadir with no initdb/import at boot.

Clean-shutdown rules: postgres uses pg_ctl -m fast stop; mysql/mariadb uses
mysqladmin shutdown / mariadb-admin shutdown. No running-datadir copies.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docker" / "split"

HRMS_DB = """# syntax=docker/dockerfile:1.7
# snapshot db image for mw-hrms (mariadb datadir with the HRMS seed already imported)
ARG BASE_IMAGE=mw-hrms:latest
FROM ${BASE_IMAGE} AS snapshot
USER root
RUN set -eux; \
    mkdir -p /var/run/mysqld /var/lib/mysql; \
    chown -R mysql:mysql /var/run/mysqld /var/lib/mysql; \
    mysql_install_db --user=mysql --datadir=/var/lib/mysql >/dev/null; \
    mysqld_safe --user=mysql --datadir=/var/lib/mysql --bind-address=127.0.0.1 & \
    for i in $(seq 1 60); do mysqladmin -u root -phrms123456 ping --silent 2>/dev/null && break; sleep 2; done; \
    mysql -u root -phrms123456 -e "CREATE DATABASE IF NOT EXISTS \`_041806a949bb7dd0\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"; \
    mysql -u root -phrms123456 _041806a949bb7dd0 < /mw-hrms-dump.sql; \
    mysql -u root -phrms123456 -e "CREATE USER IF NOT EXISTS '_041806a949bb7dd0'@'%' IDENTIFIED BY '1yMa70SeWYjkbmK9'; GRANT ALL PRIVILEGES ON \`_041806a949bb7dd0\`.* TO '_041806a949bb7dd0'@'%'; FLUSH PRIVILEGES;"; \
    mysqladmin -u root -phrms123456 shutdown; \
    rm -rf /var/lib/mysql/*.pid /var/lib/mysql/*.err /var/run/mysqld/*

FROM scratch AS runtime
COPY --from=snapshot / /
ENTRYPOINT ["/opt/saas-bench/entrypoint-db.sh"]
"""

BOOKLORE_DB = """# syntax=docker/dockerfile:1.7
# snapshot db image for mw-booklore (reuses the rebuild mysql-data datadir)
ARG BASE_IMAGE=mw-booklore:latest
FROM ${BASE_IMAGE} AS snapshot
USER root
RUN set -eux; \
    test -d /var/lib/mysql/mysql; \
    chown -R mysql:mysql /var/lib/mysql; \
    mkdir -p /run/mysqld; chown -R mysql:mysql /run/mysqld; \
    rm -f /var/lib/mysql/*.pid /var/lib/mysql/*.err /run/mysqld/*

FROM scratch AS runtime
COPY --from=snapshot / /
ENTRYPOINT ["/opt/saas-bench/entrypoint-db.sh"]
"""

PRETIX_DB = """# syntax=docker/dockerfile:1.7
# snapshot db image for mw-pretix (postgres datadir with pretix migrations applied)
ARG BASE_IMAGE=mw-pretix:latest
FROM ${BASE_IMAGE} AS snapshot
USER root
ENV PGDATA=/var/lib/postgresql/data
RUN set -eux; \
    mkdir -p "$PGDATA" /var/run/postgresql; \
    chown -R postgres:postgres "$PGDATA" /var/run/postgresql; \
    su postgres -s /bin/bash -c "initdb -D $PGDATA"; \
    echo "host all all 127.0.0.1/32 trust" >> "$PGDATA/pg_hba.conf"; \
    echo "listen_addresses = '127.0.0.1'" >> "$PGDATA/postgresql.conf"; \
    su postgres -s /bin/bash -c "pg_ctl -D $PGDATA -l /tmp/pg.log -w start"; \
    su postgres -s /bin/bash -c "psql -c \"CREATE USER pretix WITH PASSWORD 'pretix' SUPERUSER;\""; \
    su postgres -s /bin/bash -c "psql -c \"CREATE DATABASE pretix OWNER pretix;\""; \
    (cd /pretix/src && DJANGO_SETTINGS_MODULE=production_settings DATA_DIR=/data/ HOME=/pretix python3 -m pretix migrate --noinput) || true; \
    su postgres -s /bin/bash -c "pg_ctl -D $PGDATA -m fast -w stop"; \
    rm -f "$PGDATA/postmaster.pid"

FROM scratch AS runtime
COPY --from=snapshot / /
ENTRYPOINT ["/opt/saas-bench/entrypoint-db.sh"]
"""

TWENTY_DB = """# syntax=docker/dockerfile:1.7
# snapshot db image for mw-twenty (postgres datadir with twenty setup+migrations applied)
ARG BASE_IMAGE=mw-twenty:latest
FROM ${BASE_IMAGE} AS snapshot
USER root
ENV PGDATA=/var/lib/postgresql/data
RUN set -eux; \
    mkdir -p "$PGDATA" /var/run/postgresql; \
    chown -R postgres:postgres "$PGDATA" /var/run/postgresql; \
    su-exec postgres initdb -D "$PGDATA"; \
    echo "host all all 127.0.0.1/32 trust" >> "$PGDATA/pg_hba.conf"; \
    echo "listen_addresses = '127.0.0.1'" >> "$PGDATA/postgresql.conf"; \
    su-exec postgres pg_ctl -D "$PGDATA" -l /tmp/pg.log -w start; \
    su-exec postgres createdb default; \
    PG_DATABASE_URL="postgres://postgres:twenty_postgres_pass@127.0.0.1:5432/default" \
      DISABLE_CRON_JOBS_REGISTRATION=true /app/entrypoint.sh true; \
    su-exec postgres pg_ctl -D "$PGDATA" -m fast -w stop; \
    rm -f "$PGDATA/postmaster.pid"

FROM scratch AS runtime
COPY --from=snapshot / /
ENTRYPOINT ["/opt/saas-bench/entrypoint-db.sh"]
"""

OPNFORM_DB = """# syntax=docker/dockerfile:1.7
# snapshot db image for mw-opnform (postgres datadir with the opnform dump restored)
ARG BASE_IMAGE=mw-opnform:latest
FROM ${BASE_IMAGE} AS snapshot
USER root
ENV PGDATA=/var/lib/postgresql/data \
    DB_DATABASE=forge DB_USERNAME=forge DB_PASSWORD=forge
RUN set -eux; \
    PG_BIN=/usr/libexec/postgresql16; [ -d "$PG_BIN" ] || PG_BIN=/usr/bin; \
    mkdir -p "$PGDATA" /run/postgresql; \
    id postgres >/dev/null 2>&1 || adduser -D -h /var/lib/postgresql postgres; \
    chown -R postgres:postgres "$PGDATA" /run/postgresql; \
    su - postgres -s /bin/bash -c "$PG_BIN/initdb -D $PGDATA"; \
    echo "host all all 127.0.0.1/32 trust" >> "$PGDATA/pg_hba.conf"; \
    echo "listen_addresses = '127.0.0.1'" >> "$PGDATA/postgresql.conf"; \
    su - postgres -s /bin/bash -c "$PG_BIN/pg_ctl -D $PGDATA -l /tmp/pg.log -w start"; \
    su - postgres -s /bin/bash -c "psql -c \"CREATE USER forge WITH PASSWORD 'forge' SUPERUSER;\""; \
    su - postgres -s /bin/bash -c "psql -c \"CREATE DATABASE forge OWNER forge;\""; \
    su - postgres -s /bin/bash -c "pg_restore -U forge -d forge --no-owner --no-privileges /docker-entrypoint-initdb.d/opnform_dump.dump" || true; \
    su - postgres -s /bin/bash -c "$PG_BIN/pg_ctl -D $PGDATA -m fast -w stop"; \
    rm -f "$PGDATA/postmaster.pid"

FROM scratch AS runtime
COPY --from=snapshot / /
ENTRYPOINT ["/opt/saas-bench/entrypoint-db.sh"]
"""

FILES = {
    "mw-hrms/Dockerfile.db": HRMS_DB,
    "mw-booklore/Dockerfile.db": BOOKLORE_DB,
    "mw-pretix/Dockerfile.db": PRETIX_DB,
    "mw-twenty/Dockerfile.db": TWENTY_DB,
    "mw-opnform/Dockerfile.db": OPNFORM_DB,
}

SERVE = {
    "mw-hrms": "#!/bin/sh\nset -e\nexec mariadbd --user=mysql --datadir=/var/lib/mysql --bind-address=0.0.0.0\n",
    "mw-booklore": "#!/bin/sh\nset -e\nexec mariadbd --user=mysql --datadir=/var/lib/mysql --bind-address=0.0.0.0\n",
    "mw-pretix": "#!/bin/sh\nset -e\nexec su postgres -s /bin/bash -c \"postgres -D /var/lib/postgresql/data\"\n",
    "mw-twenty": "#!/bin/sh\nset -e\nexec su-exec postgres postgres -D /var/lib/postgresql/data\n",
    "mw-opnform": "#!/bin/sh\nset -e\nPG_BIN=/usr/libexec/postgresql16; [ -d \"$PG_BIN\" ] || PG_BIN=/usr/bin\nexec su - postgres -s /bin/bash -c \"$PG_BIN/postgres -D /var/lib/postgresql/data\"\n",
}


def main() -> None:
    for rel, content in FILES.items():
        path = OUT / rel
        path.write_text(content, encoding="utf-8", newline="\n")
    for image, script in SERVE.items():
        path = OUT / image / "entrypoint-db.sh"
        path.write_text(script, encoding="utf-8", newline="\n")
    print(f"wrote {len(FILES)} snapshot Dockerfiles + {len(SERVE)} serve-only db entrypoints")


if __name__ == "__main__":
    main()