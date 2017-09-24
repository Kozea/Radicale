---
layout: page
title: Versioning
permalink: /versioning/
---

This page describes how to keep track of all changes to calendars and
address books with **git** (or any other version control system).

The repository must be initialized by running `git init` in the file
system folder. Internal files of Radicale can be excluded by creating the
file `.gitignore` with the following content:
```
.Radicale.cache
.Radicale.lock
.Radicale.tmp-*
```

The configuration option `hook` in the `storage` section must be set to
the following command:
```shell
git add -A && (git diff --cached --quiet || git commit -m "Changes by "%(user)s)
```

The command gets executed after every change to the storage and commits
the changes into the **git** repository.
