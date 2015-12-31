# Radicale Dockerfile
#
# VERSION 0.2

FROM 	debian:latest

ENV 	DEBIAN_FRONTEND noninteractive

# Base packages
RUN 	apt-get update -qq && apt-get upgrade -y -qq
RUN 	apt-get install -y --no-install-recommends git ca-certificates python2.7 python-setuptools python-pip \
	build-essential libffi-dev python-dev

# Radicale installation
RUN 	pip install passlib bcrypt
RUN	mkdir -p /data/config && \ 
	cd /data
COPY 	. /data/radicale
COPY	config /data/config
RUN	cd /data/radicale && python2.7 setup.py install

# User
RUN 	useradd -d /home/radicale -m radicale && \
	mkdir -p /home/radicale/.config && \
 	ln -s /data/config /home/radicale/.config/radicale && \
 	chown -R radicale:radicale /data/config && \
	chown -R radicale:radicale /home/radicale
 
USER 	radicale
WORKDIR	/home/radicale

CMD 	["radicale", "-D", "-C", "/data/config/config"]
