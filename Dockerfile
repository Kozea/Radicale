FROM alpine:latest

MAINTAINER Radicale project "radicale@librelist.com"

ENV VERSION 1.1.1
ENV TARBALL https://github.com/Kozea/Radicale/archive/${VERSION}.tar.gz

RUN apk --update --update-cache upgrade \
      && apk add \
          python3 \
          python3-dev \
          build-base \
          libffi-dev \
          ca-certificates \
          openssl \
      && python3 -m ensurepip \
      && pip3 install --upgrade pip \
      && pip3 install passlib bcrypt

RUN wget ${TARBALL} \
    && tar xzf ${VERSION}.tar.gz \
    && cd Radicale-${VERSION} && python3 setup.py install \
    && mkdir -p /etc/radicale \
    && cp config /etc/radicale/config

EXPOSE 5232

CMD ["radicale", "-f", "-C", "/etc/radicale/config"]
