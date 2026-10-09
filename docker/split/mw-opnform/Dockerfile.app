# syntax=docker/dockerfile:1.7
#
# Split image: ONE service group per container (opnform app side).
# Runs nginx, php-fpm, queue-worker, scheduler, client -- NOT postgresql/redis.

ARG BASE_IMAGE=mw-opnform:latest
FROM ${BASE_IMAGE}

USER root
COPY opnform-app.conf /etc/supervisor/conf.d/opnform-app.conf
COPY entrypoint-app.sh /opt/saas-bench/entrypoint-app.sh
RUN chmod +x /opt/saas-bench/entrypoint-app.sh
ENTRYPOINT ["/opt/saas-bench/entrypoint-app.sh"]
