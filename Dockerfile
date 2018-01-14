FROM python:alpine

# For usage documentation see docker/README.md


# rather stable metadata
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

# Add source
ADD . /radicale/

# Install Radicale
RUN python -m pip install /radicale \
 && rm -rf /root/.cache

# shaky metadata
ARG VERSION
ARG SOURCE_COMMIT
ARG BUILD_DATE
LABEL org.label-schema.schema-version="1.0" \
      org.label-schema.description="A Free and Open-Source CalDAV and CardDAV Server." \
      org.label-schema.name="radicale" \
      org.label-schema.version=$VERSION \
      org.label-schema.usage="http://radicale.org/documentation/" \
      org.label-schema.url="http://radicale.org" \
      org.label-schema.vcs-url="https://github.com/Kozea/Radicale" \
      org.label-schema.build-date=$BUILD_DATE \
      org.label-schema.vcs-ref=$SOURCE_COMMIT
