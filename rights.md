---
layout: page
title: Authentication and Rights
permalink: /rights/
---

This page describes the format of the rights file for the `from_file`
authentication backend. The configuration option `file` in the `rights`
section must point to the rights file.

The recommended rights mehtod is `owner_only`. If access to calendars
and address books outside of the home directory of users (that's `/USERNAME/`)
is granted, clients won't detect these collections and will not show them to
the user.
This is only useful if you access calendars and address books directly via URL.

An example rights file:
```toml
# The user "admin" can read and write any collection.
[admin]
user = admin
collection = .*
permission = rw

# Block access for the user "user" to everything.
[block]
user = user
collection = .*
permission =

# Authenticated users can read and write their own collections.
[owner-write]
user = .+
collection = %(login)s/.*
permission = rw

# Everyone can read the root collection
[read]
user = .*
collection =
permission = r
```

The titles of the sections are ignored (but must be unique). The keys `user`
and `collection` contain regular expressions, that are matched against the
user name and the path of the collection. Permissions from the first
matching section are used. If no section matches, access gets denied.

The user name is empty for anonymous users. Therefore, the regex `.+` only
matches authenticated users and `.*` matches everyone (including anonymous
users).

The path of the collection is separated by `/` and has no leading or trailing
`/`. Therefore, the path of the root collection is empty.

`%(login)s` gets replaced by the user name and `%(path)s` by the path of
the collection. You can also get groups from the `user` regex in the
`collection` regex with `{0}`, `{1}`, etc.
