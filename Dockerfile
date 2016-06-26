# Radicale Dockerfile
#
# VERSION 0.3.1

FROM alpine:latest

MAINTAINER Radicale project "radicale@librelist.com"

# Base packages
RUN apk --update --update-cache upgrade \
      && apk add \
          python3 \
          python3-dev \
          build-base \
          libffi-dev \
          ca-certificates \
      && python3 -m ensurepip \
      && pip3 install --upgrade pip

# Python installation
# pip
RUN pip3 install passlib bcrypt setuptools

# Radicale installation
RUN mkdir -p /data/config

COPY . /data/radicale
COPY config /data/config

RUN cd /data/radicale && python3 setup.py install

# User
RUN adduser -h /home/radicale -D radicale \
      && mkdir -p /home/radicale/.config \
      && ln -s /data/config /home/radicale/.config/radicale \
      && chown -R radicale:radicale /data/config \
      && chown -R radicale:radicale /home/radicale

USER radicale
WORKDIR /home/radicale

CMD ["radicale", "-D", "-C", "/data/config/config"]
