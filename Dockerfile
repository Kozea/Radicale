# Radicale Dockerfile
#
# VERSION 0.1

FROM debian

COPY . /opt/radicale
WORKDIR /opt/radicale

CMD python -u radicale.py

EXPOSE 5232
