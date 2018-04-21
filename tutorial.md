---
layout: page
title: Tutorial
permalink: /tutorial/
---

You want to try Radicale but only have 5 minutes free in your calendar? Let's
go right now! You won't have the best installation ever, but it will be enough
to play a little bit with Radicale.

When everything works, you can get a [client]({{ site.baseurl }}/clients/) and
start creating calendars and address books. The server **only** binds to
localhost (is **not** reachable over the network) and you can log in with any
user name and password. If Radicale fits your needs, it may be time for
[some basic configuration](/setup/).

Follow one of the chapters below depending on your operating system.

## Linux / \*BSD

First of all, make sure that **python** 3.3 or later (**python** ≥ 3.6 is
recommended) and **pip** are installed. On most distributions it should be
enough to install the package ``python3-pip``.

Then open a console and type:

```shell
# Run the following command as root or
# add the --user argument to only install for the current user
$ python3 -m pip install --upgrade radicale
$ python3 -m radicale --config "" --storage-filesystem-folder=~/.var/lib/radicale/collections
```

Victory! Open [http://localhost:5232/](http://localhost:5232/) in your browser!
You can login with any username and password.

## Windows

The first step is to install Python. Go to
[python.org](https://python.org) and download the latest version of Python 3.
Then run the installer.
On the first window of the installer, check the "Add Python to PATH" box and
click on "Install now". Wait a couple of minutes, it's done!

Launch a command prompt and type:

```
C:\Users\User> python -m pip install --upgrade radicale
C:\Users\User> python -m radicale --config "" --storage-filesystem-folder=~/radicale/collections
```

If you are using PowerShell replace ``--config ""`` with ``--config '""'``.

Victory! Open [http://localhost:5232/](http://localhost:5232/) in your browser!
You can login with any username and password.

## MacOS

*To be written.*
