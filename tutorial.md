---
layout: page
title: Tutorial
permalink: /tutorial/
---

You want to try Radicale but only have 5 minutes free in your calendar? Let's
go right now! You won't have the best installation ever, but it will be enough
to play a little bit with Radicale.

When everything works, you can get a [client]({{ site.baseurl }}/clients/) and
start creating calendars and address books. And if Radicale fits your needs, it
may be time to for [some basic configuration](/setup/).

Follow one of the chapters below depending on your operating system.

## Linux / \*BSD

First of all, make sure that **python** 3.4 or later and **pip** are
installed. On most distributions it should be enough to install the package
``python3-pip``.

Then open a console and type:

    $ python3 -m pip install --upgrade radicale
    $ python3 -m radicale --config /dev/null --storage-filesystem-folder=~/.var/lib/radicale/collections

Victory! Open [http://localhost:5232/](http://localhost:5232/) in your browser
and enjoy the "Radicale works!" message!

## Windows

This first step is to install Python. Go to
[python.org](http://python.org) and download the latest version of Python 3.
Then run the installer.
On the first window of the installer, check the "Add Python to PATH" box and
click on "Install now". Wait a couple of minutes, it's done!

Launch a command prompt and type:

    C:\Users\MyName> python -m pip install --upgrade radicale
    C:\Users\MyName> python -m radicale --storage-filesystem-folder=~/radicale

Victory! Open [http://localhost:5232/](http://localhost:5232/) in your browser
and enjoy the "Radicale works!" message!

## MacOS

*To be written.*
