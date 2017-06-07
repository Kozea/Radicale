---
layout: page
title: WSGI
permalink: /wsgi/
---

Radicale is compatible with the WSGI specification. Use `radicale.wsgi` from
the source code as the WSGI file.

A configuration file can be set with the `RADICALE_CONFIG` environment variable,
otherwise the default configuration is used.

**Important:** The `None` authentication type disables all rights checking.
Don't use it with `REMOTE_USER`. The development version of Radicale has
the `remote_user` module for this use-case.

Be reminded that Radicale's default configuration enforces limits on the
maximum upload file size.

## Manage user accounts with the WSGI server

(This feature is only available in the development version!)

Set the configuration option `type` in the `auth` section to `remote_user`.
Radicale uses the user name provided by the WSGI server and disables
authentication over HTTP.
