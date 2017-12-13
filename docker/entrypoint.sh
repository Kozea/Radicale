#!/bin/sh

RADICALE_UID="${RADICALE_UID:-1000}"
RADICALE_GID="${RADICALE_GID:-1000}"

addgroup   -g ${RADICALE_GID} radicale
adduser -D -s /bin/false -u ${RADICALE_GID} -G radicale radicale

chown -R radicale:radicale "$(dirname "${RADICALE_CONFIG:-/etc/radicale/radicale.config}")" /var/lib/radicale

su - radicale -s /bin/sh -c "radicale --hosts 0.0.0.0:5232 ${RADICALE_CONFIG:+--config='${RADICALE_CONFIG}'} $*"
