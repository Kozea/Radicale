====================
 User Documentation
====================

:Author: Guillaume Ayoub, Daniel Aleksandersen

:Date: 2012-07-05

:Abstract: This document is a short description for installing and using the
 Radicale calendar and contact Server.

.. contents::
   :depth: 3

Installation
============

Dependencies
------------

Radicale is written in pure Python and does not depend on any librabry. It is
known to work on Python 2.6, 2.7, 3.1, 3.2 and PyPy > 1.7. The dependencies are
optional, as they are only needed for various authentication methods [#]_.

Linux and MacOS users certainly have Python already installed. For Windows
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
- `KDE KOrganizer <http://userbase.kde.org/KOrganizer/>`_
- `aCal <http://wiki.acal.me/wiki/Main_Page>`_ for `Google Android
  <http://www.android.com/>`_
- `Apple iPhone <http://www.apple.com/iphone/>`_
- `Apple iCal <http://www.apple.com/macosx/apps/>`_

More clients will be supported in the future. However, it may work with any
calendar or contact client which implements CalDAV or CardDAV specifications
too (luck is highly recommanded).


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

Lightning and Thunderbird cannot access CardDAV servers yet.

Evolution
~~~~~~~~~

Calendars
+++++++++

First of all, show the calendar page in Evolution by clicking on the calendar
icon at the bottom of the side pane. Then add a new calendar by choosing in the
menu ``File → New → Calendar``.

A new window opens. The calendar ``type`` is ``CalDAV``, and the location is
something like ``caldav://localhost:5232/user/calendar.ics/``, where you can
replace ``user`` and ``calendar`` by some strings of your choice. Calendars are
automatically created if needed.

You can fill other attributes like the color and the name, these are only used
for Evolution and are not uploaded.

Click on ``OK``, and your calendar should be ready for use.

Contacts
++++++++

*To be written*

KOrganizer
~~~~~~~~~~

*To be written*

CalDAV-Sync
~~~~~~~~~~~

CalDAV-Sync is implemented as sync adapter to integrate seamlessly with 
any calendar app and widget. Therefor you have to access it via 
``Accounts & Sync`` settings after installing it from the Market.

So, to add new calendars to your phone open ``Accounts & Sync`` settings 
and tap on ``Add account``, selecting CalDAV as type. In the next view, 
you have to switch to Manual Mode. Enter the full CalDAV URL of your Radicale 
account (e.g. http://example.com:5232/Username/) and corresponding login data.

Tap on ``Next`` and the app checks for all available calendars 
on your account, listing them in the next view. You can now select calendars 
you want to sync and set a local nickname and color for each. Hitting ``Next`` 
again brings up the last page. Enter your email address and uncheck ``Sync 
from server to phone only`` if you want to use two-way-sync.

.. note::
    CalDAV-Sync officially is in alpha state and two-way-sync is marked as 
    an experimental feature. Tough it works fine for me, using two-way-sync 
    is on your own risk!
    
Tap on ``Finish`` and you're done. You're now able to use the new calendars 
in the same way you were using Google calendars before.

CardDAV-Sync
~~~~~~~~~~~~

*To be written*

aCal
~~~~

aCal is a CalDAV client for Android. It comes with its own calendar application
and does not integrate in the Android calendar. It is a "CalDAV only" calendar,
i.e. it only works in combination with a CalDAV server. It can connect to
several calendars on the server and will display them all in one calendar. It
works nice with Radicale.

To configure aCal, start aCal, go to the ``Settings`` screen, select
``Server``, then ``Add server``. Choose ``Manual Configuration`` and select
``Advanced`` (bottom of the screen). Then enter the host name of your server,
check ``Active``, enter your user name and password. The ``Simple Domain`` of
your server is the domain part of your fully qualified host name (e.g. if your
server is ``myserver.mydomain.org``, choose ``mydomain.org``).

As ``Simple Path`` you need to specify ``/<user>`` where user is the user you
use to connect to Radicale. ``Server Name`` is the fully qualified name of your
server machine (``myserver.mydomain.org``). The ``Server Path`` is
``/<user>/``.

For ``Authentication Type`` you need to specify the method you chose for
Radicale. Check ``Use SSL`` if your Radicale is configured to use SSL.

As the last thing you need to specify the port Radicale listens to. When your
server is configured you can go back to the first ``Settings`` screen, and
select ``Calendars and Addressbooks``. You should find all the calendars that
are available to your user on the Radicale server. You can then configure each
of them (display colour, notifications, etc.).

iPhone & iPad
~~~~~~~~~~~~~

Calendars
+++++++++

For iOS devices, the setup is fairly straightforward but there are a few settings
that are critical for proper operation.

1. From the Home screen, open ``Settings``
2. Select ``Mail, Contacts, Calendars``
3. Select ``Add Account`` →  ``Other`` →  ``Add CalDAV Account``
4. Enter the server URL here, including ``https``, the port, and the user/calendar
   path, ex: ``https://myserver.domain.com:3000/bob/birthdays/``
5. Enter your username and password as defined in your server config
6. Enter a good description of the calendar in the ``Description`` field.
   Otherwise it will put the whole servername in the field.
7. Now go back to the ``Mail, Contacts, Calendars`` screen and scroll down to the
   ``Calendars`` section. You must change the ``Sync`` option to sync ``All events``
   otherwise new events won't show up on your iOS devices!

.. note::
   Everything should be working now so test creating events and make sure they stay created. 
   If you create events on your iOS device and they disappear after the fetch period,
   you probably forgot to change the sync setting in step 7. Likewise, if you create events
   on another device and they don't appear on your iPad of iPhone, then make sure your sync
   settings are correct

.. warning::
   In iOS 5.x, please check twice that the ``Sync all entries`` option is
   activated, otherwise some events may not be shown in your calendar.

Contacts
++++++++

*To be written*

iCal
~~~~

.. note::
   This description assumes you do not have any authentication or encryption
   configured. The procedure will change accordingly if you do.

Calendars
+++++++++

In iCal 4.0 or iCal 5.0:

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

.. warning::
   In iCal 5.x, please check twice that the ``Sync all entries`` option is
   activated, otherwise some events may not be shown in your calendar.

The wizard will close, leaving you in the ``Account`` tab again. The account is
now set-up. You can close the ``Preferences`` window.

.. important::
   To add a calendar to your shiny new account you have to go to the menu and
   select ``File → New Calendar → <your shiny new account>``. A new calendar
   appears in the left panel waiting for you to enter a name.

   This is needed because the behaviour of the big ``+`` button in the main
   window is confusing as you can't focus an empty account and iCal will just
   add a calendar to another account.

Contacts
++++++++

*To be written*


Complex Configuration
=====================

.. note::
   This section is written for Linux users, but can be easily adapted for
   Windows and MacOS users.

Installing the Server
---------------------

You can install Radicale thanks to the following command, with superuser
rights::

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
  # File storing the PID in daemon mode
  pid =
  # SSL flag, enable HTTPS protocol
  ssl = False
  # SSL certificate path
  certificate = /etc/apache2/ssl/server.crt
  # SSL private key
  key = /etc/apache2/ssl/server.key
  # Reverse DNS to resolve client address in logs
  dns_lookup = True


  [encoding]
  # Encoding for responding requests
  request = utf-8
  # Encoding for storing local collections
  stock = utf-8


  [acl]
  # Access method
  # Value: None | courier | IMAP | htpasswd | LDAP | PAM
  type = None

  # Usernames used for public collections, separated by a comma
  public_users = public
  # Usernames used for private collections, separated by a comma
  private_users = private

  # STARTTLS capable or local IMAP server domain name
  imap_auth_host_name = localhost
  imap_auth_host_port = 143

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
  # LDAP filter string
  # placed as X in a query of the form (&(...)X)
  # example: (objectCategory=…)(objectClass=…)(memberOf=…)
  # leave empty if no additional filter is needed
  ldap_filter = 
  # LDAP dn for initial login, used if LDAP server does not allow anonymous searches
  # Leave empty if searches are anonymous
  ldap_binddn =
  # LDAP password for initial login, used with ldap_binddn
  ldap_password =
  # LDAP scope of the search
  ldap_scope = OneLevel

  # PAM group user should be member of
  pam_group_membership =

  # Path to the Courier Authdaemon socket
  courier_socket =


  [storage]
  # Storage backend
  type = filesystem

  # Folder for storing local collections, created if not present
  filesystem_folder = ~/.config/radicale/collections


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


WSGI, CGI and FastCGI
---------------------

Radicale comes with a `WSGI <http://wsgi.org/>`_ support, allowing the software
to be used behind any HTTP server supporting WSGI such as Apache.

Moreover, it is possible to use `flup
<http://trac.saddi.com/flup/wiki/FlupServers>`_ to wrap Radicale into a CGI,
FastCGI, SCGI or AJP application, and therefore use it with Lighttpd, Nginx or
even Tomcat.

Apache and mod_wsgi
~~~~~~~~~~~~~~~~~~~

To use Radicale with Apache's ``mod_wsgi``, you first have to install the
Radicale module in your Python path and write your ``.wsgi`` file (in
``/var/www`` for example):

.. code-block:: python

   import radicale
   radicale.log.start()
   application = radicale.Application()

.. note::
   The ``[server]`` part of the configuration is ignored.

Next you have to create the Apache virtual host (adapt the configuration
to your environment):

.. code-block:: apache

   <VirtualHost *:80>
       ServerName cal.yourdomain.org

       WSGIDaemonProcess radicale user=www-data group=www-data threads=1
       WSGIScriptAlias / /var/www/radicale.wsgi

       <Directory /var/www>
           WSGIProcessGroup radicale
           WSGIApplicationGroup %{GLOBAL}
           AllowOverride None
           Order allow,deny
           allow from all
       </Directory>
   </VirtualHost>

.. warning::
   You should use the root of the (sub)domain (``WSGIScriptAlias /``), else
   some CalDAV features may not work.

If you want to use authentication with Apache, you *really* should use one of
the Apache authentication modules, instead of the ones from Radicale: they're
just better.

Deactivate any ACL module in Radicale and use your favourite Apache
authentication backend. You can then restrict the access: allow the ``alice``
user to access ``/alice/*`` URLs, and everything should work as expected.

Here is one example of Apache configuration file:

.. code-block:: apache

  <VirtualHost *:80>
      ServerName radicale.local

      WSGIDaemonProcess radicale user=radicale group=radicale threads=1
      WSGIScriptAlias / /usr/share/radicale/radicale.wsgi

      <Directory /usr/share/radicale/>
          WSGIProcessGroup radicale
          WSGIApplicationGroup %{GLOBAL}

          AuthType Basic
          AuthName "Radicale Authentication"
          AuthBasicProvider file
          AuthUserFile /usr/share/radicale/radicale.passwd
          Require valid-user

          AllowOverride None
          Order allow,deny
          allow from all

          RewriteEngine On
          RewriteCond %{REMOTE_USER}%{PATH_INFO} !^([^/]+/)\1
          RewriteRule .* - [Forbidden]
      </Directory>
  </VirtualHost>

If you're still convinced that access control is better with Radicale, you have
to add ``WSGIPassAuthorization On`` in your Apache configuration files, as
explained in `the mod_wsgi documentation
<http://code.google.com/p/modwsgi/wiki/ConfigurationGuidelines#User_Authentication>`_.

.. note::
   Read-only calendars or address books can also be served by a simple Apache
   HTTP server, as Radicale stores full-text icalendar and vcard files with the
   default configuration.


Authentication and URLs
-----------------------

If no authentication method is set, calendars are available at
``/calendar.ics/`` and ``/folder/calendar.ics/`` URLs. Else, calendars are
public, private or personal, depending on their URLs.

This section is written for calendars, but it is the same for address books.

Public Collections
~~~~~~~~~~~~~~~~~~

Public collections are available for everybody, authenticated or not.

Calendars at ``/public_user/calendar.ics/`` URLs are public. Public users are
defined in the ``acl → public_users`` configuration variable. If ``None`` is in
the list of public users, public calendars are also available at
``/calendar.ics/`` URLs.

.. important::

   Public calendars allow anybody to create calendars, leading to possible
   security problems. If you do not want to allow public calendars, just use an
   empty string in the ``acl → public_users`` configuration variable.


Private Collections
~~~~~~~~~~~~~~~~~~~

Private collections are available for all the authenticated users.

Calendars at ``/private_user/calendar`` URLs are private. Private users are
defined in the ``acl → private_users`` configuration variable. If ``None`` is
in the list of private users, private calendars are also available at
``/calendar`` URLs.


Personal Collections
~~~~~~~~~~~~~~~~~~~~

Personal collections are only available for the calendar owner.

Calendars at ``/owner/calendar`` URLs are personal. They are only available for
the authenticated user called ``owner`` (of course, you can replace ``owner`` by
any user name authorized by your authentication mechanism).


Python Versions and OS Support
==============================

TLS Support
-----------

Python 2.6 suffered `a bug <http://bugs.python.org/issue5103>`_ causing huge
timeout problems with TLS. The bug is fixed since Python 2.6.6.

IMAP authentication over TLS requires Python 3.2.

Python 2.7 and Python 3.x do not suffer this bug.

Crypt Support
-------------

With the htpasswd access, many encryption methods are available, and crypt is the
default one in Radicale. Unfortunately, the ``crypt`` module is unavailable on
Windows, you have to pick another method on this OS.

IMAP Authentication
-------------------

The IMAP authentication module relies on the imaplib module, available with 2.x
versions of Python. However, TLS is only available in Python 3.2. Older versions
of Python or a non-modern server who does not support STARTTLS can only
authenticate against ``localhost`` as passwords are transmitted in PLAIN. Legacy
SSL mode on port 993 is not supported.

LDAP Authentication
-------------------

The LDAP authentication module relies on `the python-ldap module
<http://www.python-ldap.org/>`_, and thus only works with 2.x versions
of Python.

PAM Authentication
------------------

The PAM authentication module relies on `the pam module
<http://atlee.ca/software/pam/>`_, and thus only works with 2.x versions of
Python.
