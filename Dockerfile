FROM python:3-alpine

# Version of Radicale (e.g. 3.0.x)
ARG VERSION=master
# Persistent storage for data (Mount it somewhere on the host!)
VOLUME /var/lib/radicale
# Configuration data (Put the "config" file here!)
VOLUME /etc/radicale
# TCP port of Radicale (Publish it on a host interface!)
EXPOSE 5232
# Run Radicale (Configure it here or provide a "config" file!)
CMD ["radicale", "--hosts", "0.0.0.0:5232"]

# Install dependencies
RUN apk add --no-cache gcc musl-dev libffi-dev ca-certificates openssl
# Install Radicale
RUN pip install --no-cache-dir "Radicale[bcrypt] @ https://github.com/Kozea/Radicale/archive/${VERSION}.tar.gz"
# Remove build dependencies
RUN apk del gcc musl-dev libffi-dev
