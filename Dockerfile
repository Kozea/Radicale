FROM python:alpine

# Version of Radicale (e.g. 3.0.x)
ARG VERSION=master

WORKDIR /radicale

COPY . .

# Install dependencies
RUN apk add --no-cache gcc musl-dev libffi-dev ca-certificates openssl && \
    # Install Radicale
    pip3 install --no-cache .[bcrypt] && \
    # Remove build dependencies
    apk del gcc musl-dev libffi-dev
# Persistent storage for data (Mount it somewhere on the host!)
VOLUME /var/lib/radicale
# Configuration data (Put the "config" file here!)
VOLUME /etc/radicale
# TCP port of Radicale (Publish it on a host interface!)
EXPOSE 5232
# Run Radicale (Configure it here or provide a "config" file!)
CMD ["radicale", "--hosts", "0.0.0.0:5232"]
