# syntax=docker/dockerfile:1.7
#
# Split image: ONE service per container (app).
#
# Base bundle : mw-twenty
# Entrypoint  : added by this image (entrypoint-app.sh)
#
# The app container still runs the fixture / migrations before serving; the db and
# redis containers only initialise their datadir (if empty) and then serve.

ARG BASE_IMAGE=mw-twenty:latest
FROM ${BASE_IMAGE}

USER root
COPY entrypoint-app.sh /opt/saas-bench/entrypoint-app.sh
RUN chmod +x /opt/saas-bench/entrypoint-app.sh
ENTRYPOINT ["/opt/saas-bench/entrypoint-app.sh"]
