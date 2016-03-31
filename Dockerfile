# Radicale Dockerfile
#
# VERSION 0.3

FROM 	alpine:latest

# Base packages
RUN	apk update && \
	apk upgrade && \
	apk add ca-certificates git python python-dev py-setuptools py-pip build-base libffi-dev

# Radicale installation
RUN 	pip install passlib bcrypt
RUN	mkdir -p /data/config && \
	cd /data
COPY 	. /data/radicale
COPY	config /data/config
RUN	cd /data/radicale && python2.7 setup.py install

# User
RUN 	adduser -h /home/radicale -D radicale && \
	mkdir -p /home/radicale/.config && \
 	ln -s /data/config /home/radicale/.config/radicale && \
 	chown -R radicale:radicale /data/config && \
	chown -R radicale:radicale /home/radicale

USER 	radicale
WORKDIR	/home/radicale

CMD 	["radicale", "-D", "-C", "/data/config/config"]
