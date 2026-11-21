# Components

The replaceable parts are the packages with `INTERNAL_TYPES`: `auth`, `group`, `storage`, `rights`, `web`, `sharing`, and `hook`. Those names are listed in each package's `__init__.py`. A custom plugin is a module path in the matching `type` option. It subclasses the `Base*` class and is named `Auth`, `Group`, `Storage`, `Rights`, `Web`, `Sharing`, or `Hook`. `app/`, `item/`, and `tests/` are not selected by a `type` option.

## `radicale/app/`

HTTP methods. `Application` inherits one mixin per method file:

| File | Method |
| --- | --- |
| `delete.py` | `DELETE` |
| `get.py` | `GET`, including free/busy views and the web UI hand-off |
| `head.py` | `HEAD` |
| `mkcalendar.py` | `MKCALENDAR` |
| `mkcol.py` | `MKCOL` |
| `move.py` | `MOVE` of an item, or of a calendar or address book collection |
| `options.py` | `OPTIONS` |
| `post.py` | `POST` |
| `propfind.py` | `PROPFIND` |
| `proppatch.py` | `PROPPATCH` |
| `put.py` | `PUT` |
| `report.py` | `REPORT` |
| `base.py` | Rights checks, XML read and write, path and user validation |

`__init__.py` owns authentication, principal creation, and the call into `do_*`.

## `radicale/auth/`

`[auth] type`. Internal types: `none`, `denyall`, `remote_user`, `http_remote_user`, `http_x_remote_user`, `htpasswd`, `imap`, `dovecot`, `ldap`, `oauth2`, `pam`.

`none` returns the username it was given. `BaseAuth.login` rejects an empty username before calling the backend and logs a warning. `denyall` rejects everyone. `auth.load` also logs a warning for `[auth] type` `none` and for `denyall`. The three `remote_user` types read a header or `REMOTE_USER` in `get_external_login`, which returns `environ.get(name, ""), ""`. The loopback warning is a separate branch. It runs only for those three types, and only when `os.environ.get("SERVER_GATEWAY_INTERFACE")` is missing or empty and some `[server] hosts` entry is outside `localhost`, `localhost6`, `127.0.0.1`, and `::1`. It does not read the request environ and it does not look at `[server] type`. The built-in server sets `ServerHandler.os_environ` to `{}`, so the WSGI environ is not the process environment. A typical external server sets `SERVER_GATEWAY_INTERFACE` on the request environ, which does not skip this warning.

`login` returns `(user, groups, info)`. `info` is the auth type string, with `/cached` appended on a cache hit. An empty password is rejected inside `ldap`, `pam`, `imap`, `oauth2`, and `dovecot`, not in `BaseAuth.login`. Login cache applies to `dovecot`, `ldap`, `htpasswd`, `imap`, `oauth2`, and `pam`, and only when `[auth] cache_logins` is true. The default is false. Any other auth type forces the cache off.

`htpasswd` supports bcrypt and argon2 when those extras are installed. `ldap` prefers `ldap3` and falls back to `ldap` (the `python_ldap` extra). `pam` imports `pwd` and `grp` at module import and imports the `pam` package inside `Auth.__init__`. Do not import `radicale.auth.pam` at module level in a test. See [AGENTS.md](../AGENTS.md).

## `radicale/group/`

`[group] type`: `none`, `from_auth`, `htgroup`.

`from_auth` raises `RuntimeError` unless `[auth] type` is `ldap` or `pam`. Its `_groups` returns an empty set, and `groups()` calls that. The request path does not call it. For `from_auth`, the groups on the request are the set `Auth.login` returned. `htgroup` replaces that set by reading an Apache-style group file. `radicale.auth.pam` adds the primary group and the groups from `os.getgrouplist` to the set it returns.

## `radicale/rights/`

`[rights] type`: `owner_only`, `owner_write`, `authenticated`, `from_file`.

Paths below are after `pathutils.strip_path`. A deeper path than one slash returns `""` from all three built-in backends. `_verify_user` is false when `[auth] type` is `none`. Those three backends then skip the anonymous and non-owner checks, so every caller gets the owner letters in the root, principal, and one-slash rows. A path deeper than one slash still returns `""`. When the auth type is anything else, an anonymous user gets `""` from `authenticated` and from the two backends that subclass it.

| Backend | Root | Principal (no slash) | Collection (one slash) |
| --- | --- | --- | --- |
| `authenticated` | `RW` | `RW` | `rw` |
| `owner_only` | `R` | `RW` for the owner, otherwise `""` | `rw` for the owner, otherwise `""` |
| `owner_write` | `R` | `RW` for the owner, `R` for someone else | `rw` for the owner, `r` for someone else |

`from_file` reads the rights file (`[rights] file`, example in `rights`).

`authenticated` treats the root and a principal the same: both have no slash, so both return `RW`. The root row above is that case (`sane_path` empty still has no slash). `owner_only` and `owner_write` special-case the empty path and return `R`.

Permission letters are the docstring of `radicale/rights/__init__.py`. Helpers `intersect`, `remove`, and `add` combine those strings. `Access.check` raises unless `permission` is a substring of `INTERNAL_PERMISSIONS_ITEM` (`rwdDoD`). A string such as `Do` passes that guard. An item that is not a collection is checked with the parent collection's letters.

## `radicale/storage/` and `radicale/item/`

See [data-model.md](data-model.md). `storage/multifilesystem/` splits the backend into mixins: `base`, `cache`, `create_collection`, `delete`, `discover`, `get`, `history`, `lock`, `meta`, `move`, `sync`, `upload`, `verify`.

`item/filter.py` simplifies CalDAV `REPORT` filters before the storage scans members. `get_filtered` on `BaseCollection` is the default scan. It drops members outside the time range and can mark a filter as already matched.

## `radicale/sharing/`

`[sharing] type`: `none`, `csv`, `files`. The row layout is [data-model.md](data-model.md). The HTTP management API is [SHARING.md](../SHARING.md).

`collection_by_map` exposes another user's collection under the authenticated user. `collection_by_token` exposes a collection at `/.token/...` without that user logging in. Both features default off. `permit_create_map` and `permit_create_token` control who may create those rows. Rights letters `M`, `m`, `S`, `T`, and `t` override those options per collection.

## `radicale/hook/`

`[hook] type`: `none`, `email`, `rabbitmq`.

A collection `DELETE` calls `notify` inside the storage write lock, after the storage change, once per item `get_all()` yields, when `hook.enabled` is true. A member that `get_all()` does not yield is not notified, including one omitted while `[storage] skip_broken_item` is on. A `DELETE` of one member notifies that member when `hook.enabled` is true. An empty collection does not call `notify`. A member `PUT` is a `PUT` of a path that is not already a collection, under a parent whose tag is non-empty. An existing collection, and a parent with an empty tag, are whole-collection `PUT`s. `prepare` runs before the lock with no tag and no whole-collection flag. That call treats the body as a whole collection when the path has `W` or `w` and the parent has no `w`, and predicts with `predict_tag_of_whole_collection`. It treats the body as a member, and predicts with `predict_tag_of_parent_collection`, only when the path has neither `W` nor `w` and the parent has `w`. `do_PUT` returns `NOT_ALLOWED` before the first `prepare` when the path has neither `W` nor `w` and the parent has no `w`. If the path has `W` or `w` and the parent also has `w`, the first `prepare` does not classify the request and does not append. Inside the lock, `prepare` runs again only when the lock's tag or whole-collection flag differs. That second call receives those values. When the second call is a member, the flag passed to `prepare` is false and the parent has `w`, so that call keeps the parent tag and does not predict. `do_PUT` reaches that second call only when the first `prepare` returned and the parent has `w`. On a member path whose parent has no `w` and whose own path has `W` or `w`, the first `prepare` takes the whole-collection branch. If that call returns, `do_PUT` returns `NOT_ALLOWED` before the second `prepare`. If `predict_tag_of_whole_collection` returns no tag, the first call raises `ValueError` (`Can't determine collection tag`) outside its `try`, and the handler answers 500. A whole-collection path does not use the parent-`w` test. When `write_whole_collection` is true, `prepare` always replaces the tag with `predict_tag_of_whole_collection`. A member append happens only in the call whose tag is `VCALENDAR` or `VADDRESSBOOK` after `check_and_sanitize_items` returns. `VSUBSCRIBED` passes the allowed-tag test. On a member, a component count other than one raises first, and one component then raises `ValueError` in the final branch, so the request returns 400 and does not append. A UID conflict returns 409 before `upload`. After `upload` succeeds, `notify` runs when `hook.enabled` is true. A `ValueError` from `upload` returns before `notify`. No whole-collection `PUT` calls `notify`. `PROPPATCH` notifies only when the body parsed as XML. A share-overlay `PROPPATCH` returns before that method's own `acquire_lock`. It updates the share row and does not call `set_meta` or `hook.notify`. The `csv` backend always takes a storage write lock in `database_update_sharing`. The `files` backend returns `not-found` before that lock when the share file is missing, and takes the lock when the file exists. `[storage] hook` runs after that caller returns normally and before the write lock is released. It does not run when the locked block raises. An unknown `%` placeholder is logged and the command is not started. A bad conversion of a known name, such as `%(path)d`, is not caught there and propagates. It is a shell command, not this plugin. See [data-model.md](data-model.md).

`email.enabled` is true when the SMTP host is not `None`. The default of `[hook] smtp_server` is `""`, and `""` is not `None`, so that default still counts as enabled. The constructor does not connect to SMTP. `notify` returns without sending when the item is not a calendar item.

`rabbitmq.enabled` is `self._endpoint is not None`. The schema default of `[hook] rabbitmq_endpoint` is `""`, which is not `None`. `Hook.__init__` always calls `_make_connection_synced`. That calls `pika.URLParameters` before the dry-run check. An empty string parses as `localhost` port `5672`. A `URLParameters` error fails `Hook.__init__` and `hook.load` falls back to `none` even when dry-run is on. Dry-run returns before `BlockingConnection` and before `queue_declare`. With dry-run off, a connection or `queue_declare` error also falls back to `none`, whose `enabled` is false. The blank default stays enabled only when that startup connection succeeds, or when dry-run gets past `URLParameters` and returns before the connection. The published body is `notification_item.to_json()` encoded with `[encoding] stock`. Dry-run logs `vars(notification_item)` and does not publish. With dry-run off, `ChannelWrongStateError` or `StreamLostError` calls `_make_connection_synced` and tries once more. An exception raised by that reconnect propagates. Any other publish error, or a second failure, is logged and not retried. The `rabbitmq` extra installs `pika`.

If the selected hook fails to import or construct while the application starts, the loader logs a warning, copies the configuration, sets the hook type to `none` on the copy, and continues. The application's configuration keeps the type that failed. The server still starts.

## `radicale/web/`

`[web] type`: `internal` or `none`.

`internal` serves `radicale/web/internal_data/`, except `/.web/js/config.js`, which is generated from `[web] prefer_browser_login`. `GET /.web` with no trailing slash is a directory of that tree, so the response is 302 to `base_prefix + "/.web/"`. `HEAD` does the same because it calls `GET`. Scenes live in `js/scenes/`. The CalDAV client code is in `js/api/`. Typecheck with `tsc -p radicale/web/jsconfig.json`. `integ_tests/` drives this UI with Playwright. `[web] type = none` answers `GET /.web` with status 200 and the text `Radicale works!`. The body is a string, so the sent `Content-Type` is `text/plain; charset=` plus `[encoding] request`. For `none`, any other `/.web/...` path redirects to `base_prefix + "/.web"` from `none.Web.get`, so `GET` and `HEAD` do. `internal` does not: it serves the file, answers 302 to `base_prefix + path + "/"` when the path is a directory without a trailing slash, and returns 404 when the path is missing. `POST /.web` uses `BaseWeb.post` and returns 405.

## Other modules

| Module | Role |
| --- | --- |
| `config.py` | Schema, file loading, command-line overrides |
| `httputils.py` | Status lines, request-body read, Basic decoding |
| `log.py` | Logger, `notice` and `trace` levels, conditional logging |
| `pathutils.py` | Safe path segments, filesystem names, fsync |
| `xmlutils.py` | Clark notation, content types, XML helpers |
| `utils.py` | Plugin loader, package versions, SSL protocol helpers |
| `types.py` | WSGI and config type aliases |
| `__main__.py` | CLI |
| `server.py`, `server_cheroot.py` | The three HTTP servers |

`contrib/` holds example reverse-proxy and systemd files. They are not imported by the server.
