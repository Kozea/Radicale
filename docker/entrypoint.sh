#!/bin/sh

RADICALE_UID="${RADICALE_UID:-1000}"
RADICALE_GID="${RADICALE_GID:-1000}"

getent group  radicale &> /dev/null || addgroup -g ${RADICALE_GID} radicale
getent passwd radicale &> /dev/null || adduser -D -H -s /bin/false -u ${RADICALE_GID} -G radicale radicale

if [ -n "${RADICALE_CONFIG}" ]; then
    chown -R radicale:radicale $(dirname $RADICALE_CONFIG) /var/lib/radicale
    CONF_OPT="--config '${RADICALE_CONFIG}'"
else
    chown -R radicale:radicale /etc/radicale /var/lib/radicale
    CONF_OPT=""
fi

exec su -s /bin/sh -c "exec radicale --hosts 0.0.0.0:5232 ${CONF_OPT} $*" radicale
