---
layout: page
title: Reverse Proxy
permalink: /proxy/
---

When a reverse proxy is used, the path at which Radicale is available must
be provided via the `X-Script-Name` header. The proxy must remove the location
from the URL path that is forwarded to Radicale.

Example **nginx** configuration:
```nginx
location /radicale/ { # The trailing / is important!
    proxy_pass        http://localhost:5232/; # The / is important!
    proxy_set_header  X-Script-Name /radicale;
    proxy_set_header  X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_pass_header Authorization;
}
```

Be reminded that Radicale's default configuration enforces limits on the
maximum number of parallel connections, the maximum file size and the rate of
incorrect authentication attempts. Connections are terminated after a timeout.

## Manage user accounts with the reverse proxy
Set the configuration option `type` in the `auth` section to
`http_x_remote_user`.
Radicale uses the user name provided in the `X-Remote-User` HTTP header and
disables HTTP authentication.

Example **nginx** configuration:

```nginx
location /radicale/ {
    proxy_pass           http://localhost:5232/;
    proxy_set_header     X-Script-Name /radicale;
    proxy_set_header     X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header     X-Remote-User $remote_user;
    auth_basic           "Radicale - Password Required";
    auth_basic_user_file /etc/nginx/htpasswd;
}
```

**Security:** Untrusted clients should not be able to access the Radicale
server directly. Otherwise, they can authenticate as any user.

## Secure connection between Radicale and the reverse proxy
SSL certificates can be used to encrypt and authenticate the connection between
Radicale and the reverse proxy. First you have to generate a certificate for
Radicale and a certificate for the reverse proxy. The following commands
generate self-signed certificates. You will be asked to enter additional
information about the certificate, the values don't matter and you can keep the
defaults.

```shell
$ openssl req -x509 -newkey rsa:4096 -keyout server_key.pem -out server_cert.pem -nodes -days 9999
$ openssl req -x509 -newkey rsa:4096 -keyout client_key.pem -out client_cert.pem -nodes -days 9999
```

Use the following configuration for Radicale:

```ini
[server]
ssl = True
certificate = /path/to/server_cert.pem
key = /path/to/server_key.pem
certificate_authority = /path/to/client_cert.pem
```

Example **nginx** configuration:

```nginx
location /radicale/ {
    ...
    # Place the files somewhere nginx is allowed to access (e.g. /etc/nginx/...).
    proxy_ssl_certificate         /path/to/client_cert.pem;
    proxy_ssl_certificate_key     /path/to/client_key.pem;
    proxy_ssl_trusted_certificate /path/to/server_cert.pem;
}
```
