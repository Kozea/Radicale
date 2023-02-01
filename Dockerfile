# This file is intended to be used apart from the containing source code tree.

FROM python:3-alpine as builder

# Version of Radicale (e.g. v3)
ARG VERSION=master

# Optional dependencies (e.g. bcrypt)
ARG DEPENDENCIES=bcrypt

RUN apk add --no-cache --virtual gcc libffi-dev musl-dev \
    && python -m venv /app/venv \
    && /app/venv/bin/pip install --no-cache-dir "Radicale[${DEPENDENCIES}] @ https://github.com/Kozea/Radicale/archive/${VERSION}.tar.gz"


FROM python:3-alpine

WORKDIR /app

RUN adduser radicale --home /var/lib/radicale --system --uid 1000 --disabled-password \
    && apk add --no-cache ca-certificates openssl

COPY --chown=radicale --from=builder /app/venv /app

# Persistent storage for data
VOLUME /var/lib/radicale
# TCP port of Radicale
EXPOSE 5232
# Run Radicale
ENTRYPOINT [ "/app/bin/python", "/app/bin/radicale"]
CMD ["--hosts", "0.0.0.0:5232"]

USER radicale