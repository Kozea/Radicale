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
      && python3 -m ensurepip \
      && pip3 install --upgrade pip

RUN pip3 install passlib bcrypt

RUN mkdir -p /data/config
RUN wget ${TARBALL} \
    && tar xzf ${VERSION}.tar.gz \
    && cd Radicale-${VERSION} && python3 setup.py install

COPY config /data/config

# User
RUN adduser -h /home/radicale -D radicale \
      && mkdir -p /home/radicale/.config \
      && ln -s /data/config /home/radicale/.config/radicale \
      && chown -R radicale:radicale /data/config \
      && chown -R radicale:radicale /home/radicale

USER radicale
WORKDIR /home/radicale

CMD ["radicale", "-D", "-C", "/data/config/config"]
