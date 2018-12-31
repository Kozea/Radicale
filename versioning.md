---
layout: page
title: Versioning
permalink: /versioning/
---

This page describes how to keep track of all changes to calendars and
address books with **git** (or any other version control system).

The repository must be initialized by running `git init` in the file
system folder. Its default location can be:

```
# cd /var/lib/radicale/collections # in case of globally-installed Radicale
# git init
```
or
```
$ cd ~/.var/lib/radicale/collections  # in case of user-installed Radicale
$ git init
```
 
Internal files of Radicale can be excluded by creating the
file `.gitignore` with the following content:
```
.Radicale.cache
.Radicale.lock
.Radicale.tmp-*
```

Another git configuration issue, that must be performed is user.name and user.email 
variables. You also need to do that only once per repository:

```
git config user.name "My Radicale User"
git config user.email "my_radicale_user@email.com"
``` 

The configuration option `hook` in the `storage` section must be set to
the following command:
```shell
git add -A && (git diff --cached --quiet || git commit -m "Changes by "%(user)s)
```

The command gets executed after every change to the storage and commits
the changes into the **git** repository.

In case of problems, make sure you run radicale with ``--debug`` switch and 
inspect the log output. For more information, please visit 
[section on logging.]({{ site.baseurl }}/logging/) .  
