---
layout: page
title: Tutorial
permalink: /tutorial/
---

You want to try Radicale but only have 5 minutes free in your calendar? Let's
go right now! You won't have the best installation ever, but it will be enough
to play a little bit with Radicale.

Follow one of the chapters below depending on your operating system.

When Radicale is launched, you can check that everything is OK by opening
[http://localhost:5232/](http://localhost:5232/) in your favourite browser:
you'll get a "Radicale works!" message.

When everything works, you can get a [client]({{ site.baseurl }}/clients/) and
start creating calendars and address books. And if Radicale fits your needs, it
may be time to [install it "The Right Way"]({{ site.baseurl }}/install/).

## Linux / *BSD

Installing Radicale on Linux or *BSD is often really easy.

First of all, check that you have Python 3.4 or superior installed, or install
it thanks to your package manager. Then open a console and type:

    $ pip3 install radicale
    $ python3 -m radicale --debug
    ...
    Radicale server ready

## Windows

First of all: please install all the Windows updates available for your version
of Windows! (But it's already done, isn't it?)

The next step on Windows is to intall Python. Go to
[python.org](http://python.org) and download the latest version of Python. Run
the installer.

On the first window of the installer, check the "Add Python to PATH" box and
click on "Install now". Wait a couple of minutes, it's done!

Then launch a command prompt, and type:

    C:\Users\MyName> python -m pip install radicale
    C:\Users\MyName> python -m radicale --debug
    ...
    Radicale server ready

Victory! Open [http://localhost:5232/](http://localhost:5232/) in your browser
and enjoy the "Radicale works!" message!

## OS X

*To be written.*
