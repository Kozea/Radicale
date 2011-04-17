====================
 User Documentation
====================

:Author: Guillaume Ayoub

:Date: 2010-02-11

:Abstract: This document is a short description for installing and using the
 Radicale Calendar Server.

.. contents::

Installation
============

Dependencies
------------

Radicale is written in pure python and does not depend on any librabry. It is
known to work on Python from 2.5 to 3.2 [#]_.

Linux users certainly have Python already installed. For Windows and MacOS
users, please install Python [#]_ thanks to the adequate installer.

.. [#] See `Python Versions and OS Support`_ for further information.

.. [#] `Python download page <http://python.org/download/>`_.

Radicale
--------

Radicale can be freely downloaded on the `project website, download section
<http://www.radicale.org/download>`_. Just get the file and unzip it in a
folder of your choice.

CalDAV Clients
--------------

At this time Radicale has been tested and works fine with the latests version
of:

- `Mozilla Lightning <http://www.mozilla.org/projects/calendar/lightning/>`_
- `GNOME Evolution <http://projects.gnome.org/evolution/>`_
- `Google Android <http://www.android.com/>`_
- `Apple iPhone <http://www.apple.com/iphone/>`_

More clients will be supported in the future. However, it may work with any
calendar client which implements CalDAV specifications too (luck is highly
recommanded).

To download Lightning, go to the `Lightning project website
<http://www.mozilla.org/projects/calendar/lightning/>`_ and choose the latest
version. Follow the instructions depending on your operating system.


Simple Usage
============

Starting the Server
-------------------

To start Radicale CalDAV server, you have to launch the file called
``radicale.py`` located in the root folder of the software package.

Starting the Client
-------------------

Lightning
~~~~~~~~~

After starting Lightning, click on ``File`` and ``New Calendar``. Upcoming
window asks you about your calendar storage. Chose a calendar ``On the
Network``, otherwise Lightning will use its own file system storage instead of
Radicale's one and your calendar won't be remotely accessible.

Next window asks you to provide information about remote calendar
access. Protocol used by Radicale is ``CalDAV``. A standard location for a
basic use of a Radicale calendar is ``http://localhost:5232/user/calendar/``,
where you can replace ``user`` and ``calendar`` by some strings of your
choice. Calendars are automatically created if needed.

You can now customize your calendar by giving it a nickname and a color. This
is only used by Lightning to identify calendars among others.

If no warning sign appears next to the calendar name, you can now add events
and tasks to your calendar. All events and tasks are stored in the server, they
can be accessed and modified from multiple clients by multiple users at the
same time.

Evolution
~~~~~~~~~

First of all, show the calendar page in Evolution by clicking on the calendar
icon at the bottom of the side pane. Then add a new calendar by choosing in the
menu ``File``, ``New``, ``Calendar``.

A new window opens. The calendar ``type`` is ``CalDAV``, and the location is
something like ``caldav://localhost:5232/user/calendar/``, where you can
replace ``user`` and ``calendar`` by some strings of your choice. Calendars are
automatically created if needed.

You can fill other attributes like the color and the name, these are only used
for Evolution and are not uploaded.

Click on ``OK``, and your calendar should be ready for use.

Android
~~~~~~~

*To be written*

iPhone
~~~~~~

*To be written*


Complex Configuration
=====================

.. note::
   This section is only for Linux users. Windows and MacOS advanced support
   will be available later.

Installing Server
-----------------

You can install Radicale CalDAV server with the following command, with
superuser rights::

  python setup.py install

Then, launching the server can be easily done by typing as a normal user::

  radicale

Configuring Server
------------------

Configuration File
~~~~~~~~~~~~~~~~~~

.. note::
   This section is following the latest git master changes. Please look at the
   default configuration file included in your package if you have an older
   version of Radicale.

The server configuration can be modified in ``/etc/radicale/config`` or in
``~/.config/radicale/config``. Here is the default configuration file, with the
main parameters:

.. code-block:: ini

  [server]
  # CalDAV server hostnames separated by a comma
  # IPv4 syntax: address:port
  # IPv6 syntax: [address]:port
  # IPv6 adresses are configured to only allow IPv6 connections
  hosts = 0.0.0.0:5232
  # Daemon flag
  daemon = False
  # SSL flag, enable HTTPS protocol
  ssl = False
  # SSL certificate path (if needed)
  certificate = /etc/apache2/ssl/server.crt
  # SSL private key (if needed)
  key = /etc/apache2/ssl/server.key
  
  [encoding]
  # Encoding for responding requests
  request = utf-8
  # Encoding for storing local calendars
  stock = utf-8

  [acl]
  # Access method
  # Value: None | htpasswd
  type = None
  # Personal calendars only available for logged in users (if needed)
  personal = False
  # Htpasswd filename (if needed)
  filename = /etc/radicale/users
  # Htpasswd encryption method (if needed)
  # Value: plain | sha1 | crypt
  encryption = crypt

  [storage]
  # Folder for storing local calendars,
  # created if not present
  folder = ~/.config/radicale/calendars

  [logging]
  # Logging configuration file
  # If no config is given, simple information is printed on the standard output
  # For more information about the syntax of the configuration file, see:
  # http://docs.python.org/library/logging.config.html
  config = /etc/radicale/logging
  # Set the default logging level to debug
  debug = False

This configuration file is read each time the server is launched. If some
values are not given, the default ones are used. If no configuration file is
available, all the default values are used.

Command Line Options
~~~~~~~~~~~~~~~~~~~~

All the options of the ``server`` part can be changed with command line
options. These options are available by typing::

  radicale --help


Python Versions and OS Support
==============================

TLS Support
-----------

HTTPS support depends on the ``ssl`` module, only available from Python
2.6. Nevertheless, Radicale without TLS encryption works well with Python 2.5.

Moreover, python 2.6 suffered `a bug <http://bugs.python.org/issue5103>`_
causing huge timeout problems with TLS. The bug is fixed since Python 2.6.6.

Python 2.7 and Python 3.x do not suffer this bug.

Crypt Support
-------------

With the htpasswd access, many encryption methods are available, and crypt is the
default one in Radicale. Unfortunately, the ``crypt`` module is unavailable on
Windows, you have to pick another method on this OS.
