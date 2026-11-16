# Data model

Radicale stores calendars and address books as files. The default storage type is `multifilesystem`. `multifilesystem_nolock` uses the same files and an in-process read/write lock. It does not take the `.Radicale.lock` file. Both implement `storage.BaseStorage` and `storage.BaseCollection`.

Operator details that duplicate this page belong in [DOCUMENTATION.md](../DOCUMENTATION.md) and [SHARING.md](../SHARING.md). This page is the on-disk shape the code reads and writes.

## Paths

A collection path is a sanitized URL path without a leading or trailing slash.

* Empty path: the root collection. `BaseCollection.is_principal` is false here because the path is empty.
* One segment, `user`: the principal. `is_principal` is true only when the path is non-empty and contains no slash.
* `user/calendar`: a collection owned by `user`. `BaseCollection.owner` is the first segment.

The storage folder is `[storage] filesystem_folder`. Collection files live under `collection-root/` inside that folder:

```
{filesystem_folder}/
  collection-root/
    {user}/
      .Radicale.props
      {collection}/
        .Radicale.props
        {href}
  .Radicale.lock
```

A member `PUT` stores the file under the URL basename, such as `event.ics`. A whole-collection `PUT` names each file from the item UID. The suffix is `.ics` for `VCALENDAR` and `.vcf` for `VADDRESSBOOK`. If the UID already ends with that suffix (case-insensitive), that name is the first candidate. Otherwise the first candidate is the UID plus that suffix, so a calendar UID `contact.vcf` has first candidate `contact.vcf.ics`. The next candidate is the unquoted SHA-256 hex digest of the UID (`get_etag(uid).strip('"')`) plus the suffix, then a generated name. The first free safe name is opened. If that `open` raises `OSError`, a later free safe name is tried only when the platform is not Windows and `errno` is `EINVAL`, or the platform is Windows and `errno` is 123. That handler covers both platforms. Any other `OSError` is re-raised. If no candidate can be opened, the loop raises `RuntimeError`. A file is an item. `_list` yields only files whose names pass `is_safe_filesystem_path_component`. A file that fails that check and starts with `.Radicale` is ignored. Any other unsafe file name is logged and skipped. A directory is not an item. `discover` yields it as a child collection only when the name passes `is_safe_filesystem_path_component`. A name that starts with `.` fails that check, so `.Radicale.cache` and `.Radicale.tmp-*` are not child collections. An unsafe directory name that does not start with `.Radicale` is logged and skipped.

## Collection metadata

`.Radicale.props` is a JSON object of string properties. `CollectionPartMeta` reads and writes it. The `tag` property is the collection kind:

| `tag` | Meaning |
| --- | --- |
| `VCALENDAR` | Calendar. Members are iCalendar objects. |
| `VADDRESSBOOK` | Address book. Members are vCards. |
| `VSUBSCRIBED` | A subscribed collection (`CS:subscribed`). |

`item.check_and_sanitize_props` rejects a `tag` outside those three values and `""`.

The collection etag is a quoted SHA-256 over each member's `href`, that member's etag, and the JSON metadata with sorted keys. `BaseCollection.sync` builds `http://radicale.org/ns/sync/` plus that etag without quotes. An empty old token returns the current member hrefs. Any non-empty token raises `ValueError`. The multifilesystem backend does not use that etag as the token. It hashes `href + "/" + history_etag` for current items and for deleted hrefs still in the history cache, and stores that state with pickle under the cache directory described below. An empty old token returns every href in that state. A well-formed stored token that differs from the token just computed returns the changed hrefs. If that old state file is missing, it raises `ValueError`. A `pickle.UnpicklingError`, or a `ValueError` from `pickle.load`, is logged. `os.remove` is then attempted. `FileNotFoundError` and `PermissionError` are suppressed, and `PermissionError` leaves the file in place. Any other error from `os.remove` propagates. If `os.remove` returns or its error is suppressed, the function raises a new `ValueError` (`Token not found`). A token equal to the one just computed returns no changes and does not open a state file. A malformed token raises `ValueError`.

## Items

`radicale.item.Item` wraps one vObject component. The text is parsed with `vobject`. The item's own etag is a quoted SHA-256 of `serialize()`. Upload writes the member file through `_atomic_write`. That helper creates a `.Radicale.tmp-*` directory inside the collection (the parent of the member file), then replaces the destination.

A whole-collection PUT copies `X-WR-CALNAME` and `X-WR-CALDESC` from the first item to `D:displayname` and `C:calendar-description` only when the collection tag is `VCALENDAR`, the body parsed to at least one item, and the value is non-empty. An empty value is ignored. A non-calendar collection does not copy them.

`[storage] skip_broken_item` controls a member that fails while its item cache is filled. On a cache miss, the `except Exception` covers decoding the file text, `read_components`, `check_and_sanitize_items`, unpacking the single component, constructing the item, and storing the item cache. When the option is on, `_get` logs `Skip broken item` and raises `ValueError`. `get_all` and `get_multi` catch that and omit the member. `discover` of that exact href catches `ValueError` and yields nothing. `discover` with a depth other than `"0"` calls `_get` on each child file and catches `ValueError` inside the child context manager. The default context manager, which `PROPFIND` uses, omits that child and continues. Any other context manager makes `discover` raise a new `ValueError`, which that context manager then sees. `verify` passes a context manager that catches `ValueError` and other `Exception` values, not `BaseException`, and continues. A `ValueError` is counted only when the href is set, and it is not logged. Any other `Exception` is counted and logged. When the option is off, `_get` raises `RuntimeError` with message `Failed to load item %r in %r: %s`. `discover`, `get_all`, and `get_multi` do not catch that `RuntimeError`. The `verify` context manager still catches it, because `RuntimeError` is an `Exception`.

`[storage] strict_preconditions` rejects a `PUT` of an existing collection or member that has no `If-Match`. A present `If-Match` that does not match, and `If-None-Match: *` on an existing collection or member, are enforced whether or not the option is on. `DELETE` treats a missing `If-Match` as `*`. A present `If-Match` that is not `*` and does not match the item etag is rejected whether or not the option is on.

## Cache

Parsed items, history, and sync tokens can be cached under `.Radicale.cache/` inside the collection, in subfolders `item`, `history`, and `sync-token`.

Each of `[storage] use_cache_subfolder_for_item`, `use_cache_subfolder_for_history`, and `use_cache_subfolder_for_synctoken` moves only that one subfolder. The moved path keeps the principal. A collection `user/calendar` is `{cache_root}/collection-cache/user/calendar/.Radicale.cache/{item|history|sync-token}`. `cache_root` is `[storage] filesystem_cache_folder` when that option is set, otherwise the storage folder. A flag that is false leaves that subfolder inside the collection: `{filesystem_folder}/collection-root/user/calendar/.Radicale.cache/{item|history|sync-token}`.

`storage.CACHE_VERSION` mixes a Radicale cache-structure version (`CACHE_VERSION_RADICALE` in `radicale/storage/__init__.py`) with the installed `vobject` version. Only the item-cache hash and the mtime-and-size stamp include it. History pickles and sync-token pickles do not, so changing `CACHE_VERSION_RADICALE` does not invalidate those files.

`[storage] use_mtime_and_size_for_item_cache` lets a read skip opening the member file when the cache stamp still matches.

## Locks

`.Radicale.lock` sits in the storage folder for `multifilesystem`. A collection create, upload, or delete takes the write lock. A read takes the read lock. That read lock is not a promise that no file is written. `collection.sync()` can write history and sync-token pickles, including while a read lock is held. It rewrites a history file only when the stored etag differs. That history update runs before the equal-token check. A token equal to the one just computed returns then. It does not open a sync-token state file and does not call `utime`. When the computed token differs from the old one, the new sync-token file is written with pickle if it is missing, and touched with `utime` if it exists, but only after an empty old token or a successful load of the old state. A `PermissionError` on that write is ignored. A `FileNotFoundError` from that `utime` is ignored. If the old token is non-empty and its state file is missing, the function raises `ValueError` (`Token not found`) and does not write the new sync-token file or call `utime`. If `pickle.load` raises `UnpicklingError` or `ValueError`, that is logged and `os.remove` is attempted. `FileNotFoundError` and `PermissionError` are suppressed, and `PermissionError` leaves the file in place. Any other error from `os.remove` propagates. If `os.remove` returns or its error is suppressed, the function raises `ValueError` (`Token not found`). None of these outcomes writes the new sync-token file or calls `utime`. A `REPORT` sync-collection on a `VCALENDAR` or `VADDRESSBOOK` calls `sync()` while it still holds the read lock. Any other collection tag, including `VSUBSCRIBED`, returns the supported-report error and does not call `sync()`. `PROPFIND` that asks for the value of `CS:getctag` or `D:sync-token` calls `sync()` after the read lock is released, and only when the collection tag is `VCALENDAR`, `VADDRESSBOOK`, or `VSUBSCRIBED`. Any other target answers 404 for those properties and does not call `sync()`. A `D:propname` request lists names and does not call `sync()`. `--verify-storage` holds the read lock around `verify()`. `verify` calls `collection.sync()` only when `item_errors` did not increase while reading that path and the collection tag is non-empty. A logged UID conflict does not increase `item_errors`. `sync()` still runs when the tag is also non-empty. `verify` also sets `_filesystem_fsync` false and does not restore it. A cache miss in `_get` can write the item cache while the storage lock mode is `"r"`. A collection `DELETE` calls `hook.notify` inside that write lock, after the storage change, once per item `get_all()` yields, when `hook.enabled` is true. A member that `get_all()` does not yield is not notified, including one omitted while `[storage] skip_broken_item` is on. A `DELETE` of one member notifies that member when `hook.enabled` is true. An empty collection builds an empty list and does not call `notify`. A member `PUT` is a `PUT` of a path that is not already a collection, under a parent whose tag is non-empty. An existing collection, and a parent with an empty tag, are whole-collection `PUT`s. `prepare` runs before the lock with no tag and no whole-collection flag. That call treats the body as a whole collection when the path has `W` or `w` and the parent has no `w`, and predicts with `predict_tag_of_whole_collection`. It treats the body as a member, and predicts with `predict_tag_of_parent_collection`, only when the path has neither `W` nor `w` and the parent has `w`. `do_PUT` returns `NOT_ALLOWED` before the first `prepare` when the path has neither `W` nor `w` and the parent has no `w`. If the path has `W` or `w` and the parent also has `w`, the first `prepare` does not classify the request and does not append. Inside the lock, `prepare` runs again only when the lock's tag or whole-collection flag differs. That second call receives those values. When the second call is a member, the flag passed to `prepare` is false and the parent has `w`, so that call keeps the parent tag and does not predict. `do_PUT` reaches that second call only when the first `prepare` returned and the parent has `w`. On a member path whose parent has no `w` and whose own path has `W` or `w`, the first `prepare` takes the whole-collection branch. If that call returns, `do_PUT` returns `NOT_ALLOWED` before the second `prepare`. If `predict_tag_of_whole_collection` returns no tag, the first call raises `ValueError` (`Can't determine collection tag`) outside its `try`, and the handler answers 500. A whole-collection path does not use the parent-`w` test. When `write_whole_collection` is true, `prepare` always replaces the tag with `predict_tag_of_whole_collection`. A member append happens only in the call whose tag is `VCALENDAR` or `VADDRESSBOOK` after `check_and_sanitize_items` returns. `VSUBSCRIBED` passes the allowed-tag test. On a member, a component count other than one raises first, and one component then raises `ValueError` in the final branch, so the request returns 400 and does not append. A UID conflict returns 409 before `upload`. After `upload` succeeds, `notify` runs when `hook.enabled` is true. A `ValueError` from `upload` returns before `notify`. No whole-collection `PUT` calls `hook.notify`. `prepare` fills the iterator for a whole-collection `VCALENDAR` or `VADDRESSBOOK`, and `create_collection` consumes it before the `notify` loop. A whole-collection `PUT` of any other tag never fills the iterator. `PROPPATCH` notifies only when the body parsed as XML and `hook.enabled` is true. A normal empty body still calls `set_meta` and does not notify. A share-overlay `PROPPATCH` returns before that method's own `acquire_lock`. It updates the share row and does not call `set_meta` or `hook.notify`. The `csv` backend always takes a storage write lock inside `database_update_sharing`. The `files` backend returns `not-found` before that lock when the share file is missing, and takes the lock when the file exists. `[storage] hook`, when set, is a shell command run by `StoragePartLock.acquire_lock` after the caller returns normally and before the write lock is released. It does not run when the locked block raises. An unknown `%` placeholder is logged and the command is not started. A bad conversion of a known name, such as `%(path)d`, is not caught there and propagates. It is not the `radicale.hook` plugin. Filesystem `fsync` is controlled by the internal option `[storage] _filesystem_fsync` (tests turn it off).

## Sharing database

Sharing is not a second copy of the calendar. Creating a share discovers `PathMapped` and rejects a missing collection. An update can store a new `PathMapped` without discovering that new path. The row fields are `DB_FIELDS_V1` in `radicale/sharing/__init__.py`:

`ShareType`, `PathOrToken`, `PathMapped`, `Conversion`, `Owner`, `User`, `Permissions`, `EnabledByOwner`, `EnabledByUser`, `HiddenByOwner`, `HiddenByUser`, `TimestampCreated`, `TimestampUpdated`, `Properties`, `Actions`.

`ShareType` is `token` or `map`. `Conversion` `bday` builds a calendar of recurring events from contact birthdays. `Properties` and `Actions` are dicts in memory. The comments in `radicale/sharing/__init__.py` call both JSON. The `csv` backend writes the row with `csv.DictWriter` (delimiter `;`) and loads those two fields with `ast.literal_eval`, not `json.loads`. The `files` backend stores `(version, row)` with `pickle`. `config.view` `freebusy` serves free/busy on a token `GET` or `HEAD`.

The database backend is `[sharing] type` (`none`, `csv`, or `files`). The log line calls this `sharing.database_type`. The config key is `type`.

| `[sharing] type` | Default location when `database_path` is empty |
| --- | --- |
| `none` | No database. `verify` returns false. |
| `csv` | `{filesystem_folder}/collection-db/sharing.csv` |
| `files` | `{filesystem_folder}/collection-db/files/{token,map}/`, one file per encoded `PathOrToken` |

`[sharing] database_path` replaces the default. For `csv` it is the CSV file path. For `files` it is the directory, and `token/` and `map/` are still created under it. The management API is described in [SHARING.md](../SHARING.md). If both `collection_by_map` and `collection_by_token` are false, `BaseSharing.__init__` sets itself disabled and returns before `_init_db`, so it calls neither `database_init` nor `database_get_info`. `verify` still calls `_init_db`, including from `--verify-sharing`.

## Group collections

`[group] group_collections_folder` (default `GROUPS`) is a directory name under `collection-root`. When `discover` depth is not `"0"` and the user has groups, discovery looks in that directory for a child whose name is `base64.b64encode(group.encode("utf-8")).decode("ascii")`. The search is skipped when the directory is missing. On a filesystem that is not case-sensitive, storage sets its `_group_collections_folder` attribute to `""` and skips that search. The config value is unchanged. `from_file` rejects `u` and `U` in a rights file. Sharing puts `u` on a group's `Permissions`, and group resolution rewrites that `u` to `U`. They are not directory names.
