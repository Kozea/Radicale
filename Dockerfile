FROM alpine:latest

# Version of Radicale (e.g. 2.0.0)
ARG VERSION=master

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
# Install Radicale
RUN wget --quiet https://github.com/Kozea/Radicale/archive/${VERSION}.tar.gz --output-document=radicale.tar.gz && \
    tar xzf radicale.tar.gz && \
    python3 -m pip install ./Radicale-${VERSION} && \
    rm -r radicale.tar.gz Radicale-${VERSION}
# Persistent storage for data (Mount it somewhere on the host!)
VOLUME /var/lib/radicale
# Configuration data (Put the "config" file here!)
VOLUME /etc/radicale
# TCP port of Radicale (Publish it on a host interface!)
EXPOSE 5232
# Run Radicale (Configure it here or provide a "config" file!)
CMD ["radicale", "--hosts", "0.0.0.0:5232"]
