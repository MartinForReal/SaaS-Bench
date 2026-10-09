# One-service image: ownCloud Apache application only.
FROM mw-owncloud-server:latest
ENTRYPOINT ["/usr/bin/entrypoint", "/usr/sbin/apache2ctl", "-D", "FOREGROUND"]
