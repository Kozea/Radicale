---
layout: page
title: WSGI
permalink: /wsgi/
---

Radicale is compatible with the WSGI specification.

A configuration file can be set with the `RADICALE_CONFIG` environment variable,
otherwise no configuration file is loaded and the default configuration is used.

Be reminded that Radicale's default configuration enforces limits on the
maximum upload file size.

**Security:** The `None` authentication type disables all rights checking.
Don't use it with `REMOTE_USER`. Use `remote_user` instead.

Example **uWSGI** configuration:

```ini
[uwsgi]
http-socket = 127.0.0.1:5232
processes = 8
plugin = python3
module = radicale
env = RADICALE_CONFIG=/etc/radicale/config
```

Example **Gunicorn** configuration:

```shell
gunicorn --bind '127.0.0.1:5232' --workers 8 --env 'RADICALE_CONFIG=/etc/radicale/config' radicale
```

## Manage user accounts with the WSGI server
Set the configuration option `type` in the `auth` section to `remote_user`.
Radicale uses the user name provided by the WSGI server and disables
authentication over HTTP.
