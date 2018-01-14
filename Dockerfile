FROM python:alpine

# For usage documentation see docker/README.md


# metadata
ENTRYPOINT ["/radicale/docker/entrypoint.sh"]
EXPOSE 5232
VOLUME ["/etc/radicale", "/var/lib/radicale"]


# Install dependencies
RUN apk add --no-cache \
      ca-certificates \
      openssl \
 && apk add --no-cache --virtual .builddeps \
      build-base \
      libffi-dev \
      python3-dev \
 && python -m pip install \
      bcrypt \
      passlib \
 && apk del .builddeps

ADD . /radicale/

# Install Radicale
RUN python -m pip install /radicale \
 && rm -rf /root/.cache
