---
layout: page
title: Storage
permalink: /storage/
---

This document describes the layout and format of the file system storage
(`multifilesystem` backend).

It's safe to access and manipulate the data by hand or with scripts.
Scripts can be invoked manually, periodically (e.g. with
[cron](https://manpages.debian.org/unstable/cron/cron.8.en.html)) or after each
change to the storage with the configuration option `hook` in the `storage`
section (e.g. [Git Versioning]({{ site.baseurl }}/versioning/)).

## Layout

The file system contains the following files and folders:

  * `.Radicale.lock`: The lock file for locking the storage.
  * `collection-root`: This folder contains all collections and items.

A collection is represented by a folder. This folder may contain the file
`.Radicale.props` with all WebDAV properties of the collection encoded
as [JSON](https://en.wikipedia.org/wiki/JSON).

An item is represented by a file containing the iCalendar data.

All files and folders, whose names start with a dot but not `.Radicale.`
(internal files) are ignored.

If you introduce syntax errors in any of the files, all requests that access
the faulty data will fail. The logging output should contain the names of the
culprits.

Future releases of Radicale 2.x.x will store caches and sync-tokens in the
`.Radicale.cache` folder inside of collections.
This folder may be created or modified, while the storage is locked for shared
access.
In theory, it should be safe to delete the folder. Caches will be recreated
automatically and clients will be told that their sync-token isn't valid
anymore.

You may encounter files or folders that start with `.Radicale.tmp.`.
Radicale uses them for atomic creation and deletion of files and folders.
They should be deleted after requests are finished but it's possible that
they are left behind when Radicale or the computer crashes.
It's safe to delete them.

## Locking

When the data is accessed by hand or by an externally invoked script,
the storage must be locked. The storage can be locked for exclusive or
shared access. It prevents Radicale from reading or writing the file system.
The storage is locked with exclusive access while the `hook` runs.

### Linux shell scripts

Use the
[flock](https://manpages.debian.org/unstable/util-linux/flock.1.en.html)
utility.

```shell
# Exclusive
$ flock --exclusive /path/to/storage/.Radicale.lock COMMAND
# Shared
$ flock --shared /path/to/storage/.Radicale.lock COMMAND
```

### Linux and MacOS

Use the
[flock](https://manpages.debian.org/unstable/manpages-dev/flock.2.en.html)
syscall. Python provides it in the
[fcntl](https://docs.python.org/3/library/fcntl.html#fcntl.flock) module.

### Windows
Use
[LockFile](https://msdn.microsoft.com/en-us/library/windows/desktop/aa365202%28v=vs.85%29.aspx)
for exclusive access or
[LockFileEx](https://msdn.microsoft.com/en-us/library/windows/desktop/aa365203%28v=vs.85%29.aspx)
which also supports shared access. Setting `nNumberOfBytesToLockLow` to `1`
and `nNumberOfBytesToLockHigh` to `0` works.
