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
known to work on Python 2.6, 2.7, 3.1 and 3.2 [#]_. The only optional
dependency is `the python-ldap module <http://www.python-ldap.org/>`_ for LDAP
authentication.

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
- `Apple iCal <http://www.apple.com/macosx/apps/>`_

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
menu ``File → New → Calendar``.

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

iCal
~~~~

.. note::
   This description assumes you do not have any authentication or encryption
   configured. The procedure will change accordingly if you do.

In iCal 4.0:

1. Open the ``Preferences`` dialog and select the ``Accounts`` tab
2. Click the ``+`` button at the lower left to open the account creation wizard
3. As ``Account type`` select ``CalDAV``
4. Select any ``User name`` you like
5. The ``Password`` field can be left empty (we did not configure
   authentication)
6. As ``Server address`` use ``domain:port``, for example ``localhost:5232``
   (this would be the case if you start an unconfigured radicale on your local
   machine)

Click ``Create``. The wizard will now tell you, that no encryption is in place
(``Unsecured Connection``). This is expected and will change if you configure
radicale to use SSL. Click ``Continue``.

The wizard will close, leaving you in the ``Account`` tab again.

.. note::
   You *might* want to change the ``Server path`` in the ``Server settings``
   panel as iCal uses your Mac Account name as the default path and not the
   ``User name`` you chose in the wizard.

The account is now set-up. You can close the ``Preferences`` window.

.. important::
   To add a calendar to your shiny new account you have to go to the menu and
   select ``File → New Calendar → <your shiny new account>``. A new calendar
   appears in the left panel waiting for you to enter a name.

   This is needed because the behaviour of the big ``+`` button in the main
   window is confusing as you can't focus an empty account and iCal will just
   add a calendar to another account.


Complex Configuration
=====================

.. note::
   This section is written for Linux users, but can be easily adapted for
   Windows and MacOS users.

Installing the Server
---------------------

You can install Radicale CalDAV server with the following command, with
superuser rights::

  python setup.py install

Then, launching the server can be easily done by typing as a normal user::

  radicale

Configuring the Server
----------------------

Main Configuration File
~~~~~~~~~~~~~~~~~~~~~~~

.. note::
   This section is following the latest git master changes. Please look at the
   default configuration file included in your package if you have an older
   version of Radicale.

The server configuration can be modified in ``/etc/radicale/config`` or in
``~/.config/radicale/config``. You can also set the ``RADICALE_CONFIG``
environment variable to a path of your choice. Here is the default
configuration file, with the main parameters:

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
  # SSL certificate path
  certificate = /etc/apache2/ssl/server.crt
  # SSL private key
  key = /etc/apache2/ssl/server.key

  [encoding]
  # Encoding for responding requests
  request = utf-8
  # Encoding for storing local calendars
  stock = utf-8

  [acl]
  # Access method
  # Value: None | htpasswd | LDAP
  type = None
  # Usernames used for public calendars, separated by a comma
  public_users = public
  # Usernames used for private calendars, separated by a comma
  private_users = private
  # Htpasswd filename
  htpasswd_filename = /etc/radicale/users
  # Htpasswd encryption method
  # Value: plain | sha1 | crypt
  htpasswd_encryption = crypt
  # LDAP server URL, with protocol and port
  ldap_url = ldap://localhost:389/
  # LDAP base path
  ldap_base = ou=users,dc=example,dc=com
  # LDAP login attribute
  ldap_attribute = uid
  # LDAP dn for initial login, used if LDAP server does not allow anonymous searches
  # Leave empty if searches are anonymous
  ldap_binddn =
  # LDAP password for initial login, used with ldap_binddn
  ldap_password =

  [storage]
  # Folder for storing local calendars, created if not present
  folder = ~/.config/radicale/calendars

  [logging]
  # Logging configuration file
  # If no config is given, simple information is printed on the standard output
  # For more information about the syntax of the configuration file, see:
  # http://docs.python.org/library/logging.config.html
  config = /etc/radicale/logging
  # Set the default logging level to debug
  debug = False
  # Store all environment variables (including those set in the shell)
  full_environment = False

This configuration file is read each time the server is launched. If some
values are not given, the default ones are used. If no configuration file is
available, all the default values are used.


Logging Configuration File
~~~~~~~~~~~~~~~~~~~~~~~~~~

Radicale uses the default logging facility for Python. The default
configuration prints the information messages to the standard output. It is
possible to print debug messages thanks to::

  radicale --debug

Radicale can also be configured to send the messages to the console, logging
files, syslog, etc. For more information about the syntax of the configuration
file, see: http://docs.python.org/library/logging.config.html. Here is an
example of logging configuration file:

.. code-block:: ini

  # Loggers, handlers and formatters keys

  [loggers]
  # Loggers names, main configuration slots
  keys = root

  [handlers]
  # Logging handlers, defining logging output methods
  keys = console,file

  [formatters]
  # Logging formatters
  keys = simple,full


  # Loggers

  [logger_root]
  # Root logger
  level = DEBUG
  handlers = console,file


  # Handlers

  [handler_console]
  # Console handler
  class = StreamHandler
  level = INFO
  args = (sys.stdout,)
  formatter = simple

  [handler_file]
  # File handler
  class = FileHandler
  args = ('/var/log/radicale',)
  formatter = full


  # Formatters

  [formatter_simple]
  # Simple output format
  format = %(message)s

  [formatter_full]
  # Full output format
  format = %(asctime)s - %(levelname)s: %(message)s


Command Line Options
~~~~~~~~~~~~~~~~~~~~

All the options of the ``server`` part can be changed with command line
options. These options are available by typing::

  radicale --help


Authentication and URLs
-----------------------

If no authentication method is set, calendars are available at ``/calendar``
and ``/folder/calendar`` URLs. Else, calendars are public, private or personal,
depending on their URLs.

Public Calendars
~~~~~~~~~~~~~~~~

Public users are available for everybody, authenticated or not.

Calendars at ``/public_user/calendar`` URLs are public. Public users are
defined in the ``acl → public_users`` configuration variable. If ``None`` is in
the list of public users, public calendars are also available at ``/calendar``
URLs.

.. important::

   Public calendars allow anybody to create calendars, leading to possible
   security problems. If you do not want to allow public calendars, just use an
   empty string in the ``acl → public_users`` configuration variable.


Private Calendars
~~~~~~~~~~~~~~~~~

Private calendars are available for all the authenticated users.

Calendars at ``/private_user/calendar`` URLs are private. Private users are
defined in the ``acl → public_users`` configuration variable. If ``None`` is in
the list of private users, private calendars are also available at
``/calendar`` URLs.


Personal Calendars
~~~~~~~~~~~~~~~~~~

Personal calendars are only available for the calendar owner.

Calendars at ``/owner/calendar`` URLs are personal. They are only available for
the authenticated user called ``owner``.


Python Versions and OS Support
==============================

TLS Support
-----------

Python 2.6 suffered `a bug <http://bugs.python.org/issue5103>`_ causing huge
timeout problems with TLS. The bug is fixed since Python 2.6.6.

Python 2.7 and Python 3.x do not suffer this bug.

Crypt Support
-------------

With the htpasswd access, many encryption methods are available, and crypt is the
default one in Radicale. Unfortunately, the ``crypt`` module is unavailable on
Windows, you have to pick another method on this OS.

LDAP Authentication
-------------------

The LDAP authentication module relies on `the python-ldap module
<http://www.python-ldap.org/>`_, and thus only works with 2.x versions
of Python.
