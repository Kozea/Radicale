FROM alpine:latest

# For documentation see docker folder

# Install dependencies
RUN apk add --no-cache \
      ca-certificates \
      openssl \
      python3 && \
    apk add --no-cache --virtual .deps \
      build-base \
      libffi-dev \
      python3-dev && \
    python3 -m pip install \
      bcrypt \
      passlib && \
    apk del .deps

ADD . /srv/radicale/

# Install Radicale
RUN python3 -m pip install /srv/radicale

VOLUME /var/lib/radicale
VOLUME /etc/radicale
EXPOSE 5232
ENTRYPOINT ["/srv/radicale/docker/entrypoint.sh"]
