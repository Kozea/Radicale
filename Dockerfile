# This file is intended to be used apart from the containing source code tree.

FROM python:3-alpine

# Version of Radicale (e.g. v3)
ARG VERSION=master
# Persistent storage for data
VOLUME /var/lib/radicale
# TCP port of Radicale
EXPOSE 5232
# Run Radicale
CMD ["radicale", "--hosts", "0.0.0.0:5232"]

RUN apk add --no-cache ca-certificates openssl \
 && apk add --no-cache --virtual .build-deps gcc libffi-dev musl-dev \
 && pip install --no-cache-dir "Radicale[bcrypt] @ https://github.com/Kozea/Radicale/archive/${VERSION}.tar.gz" \
 && apk del .build-deps
