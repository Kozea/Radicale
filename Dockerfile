FROM alpine:latest

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
# Persistent storage for data (Mount it somewhere on the host!)
VOLUME /var/lib/radicale
# Configuration data (Put the "config" file here!)
VOLUME /etc/radicale
# TCP port of Radicale (Publish it on a host interface!)
EXPOSE 5232
# Run Radicale (Configure it here or provide a "config" file!)
CMD ["radicale", "--hosts", "0.0.0.0:5232"]
