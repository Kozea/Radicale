====================
 User Documentation
====================

:Author: Guillaume Ayoub, Daniel Aleksandersen

:Date: 2013-07-09

:Abstract: This document is a description for installing and using the Radicale
 calendar and contact Server.

.. editable::

.. contents::
   :depth: 3

Installation
============

Dependencies
------------

Radicale is written in pure Python and does not depend on any library. It is
known to work on Python 2.6, 2.7, 3.1, 3.2, 3.3, 3.4 and PyPy > 1.9. The
dependencies are optional, as they are only needed for various authentication
methods [#]_.

Linux and MacOS users certainly have Python already installed. For Windows
users, please install Python [#]_ thanks to the adequate installer.

.. [#] See `Python Versions and OS Support`_ for further information.

.. [#] `Python download page <http://python.org/download/>`_.

Radicale
--------

Radicale can be freely downloaded on the `project website, download section
<http://www.radicale.org/download>`_. Just get the file and unzip it in a
folder of your choice.

CalDAV and CardDAV Clients
--------------------------

At this time Radicale has been tested and works fine with the latest version
of:

- `Mozilla Lightning <http://www.mozilla.org/projects/calendar/lightning/>`_
- `GNOME Evolution <http://projects.gnome.org/evolution/>`_
- `KDE KOrganizer <http://userbase.kde.org/KOrganizer/>`_
- `aCal <http://wiki.acal.me/wiki/Main_Page>`_,
  `ContactSync <https://play.google.com/store/apps/details?id=com.vcard.android.free>`_, 
  `CalendarSync <https://play.google.com/store/apps/details?id=com.icalparse.free>`_, 
  `CalDAV-Sync <https://play.google.com/store/apps/details?id=org.dmfs.caldav.lib>`_
  `CardDAV-Sync <https://play.google.com/store/apps/details?id=org.dmfs.carddav.Sync>`_
  and `DAVdroid <http://davdroid.bitfire.at>`_ for `Google Android <http://www.android.com/>`_
- `InfCloud <http://www.inf-it.com/open-source/clients/infcloud/>`_,
  `CalDavZAP <http://www.inf-it.com/open-source/clients/caldavzap/>`_,
  `CardDavMATE <http://www.inf-it.com/open-source/clients/carddavmate/>`_
- `Apple iPhone <http://www.apple.com/iphone/>`_
- `Apple Calendar <http://www.apple.com/macosx/apps/#calendar>`_
- `Apple Contacts <http://www.apple.com/macosx/apps/#contacts>`_
- `syncEvolution <https://syncevolution.org/>`_

More clients will be supported in the future. However, it may work with any
calendar or contact client which implements CalDAV or CardDAV specifications
too (luck is highly recommended).


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
basic use of a Radicale calendar is
``http://localhost:5232/user/calendar.ics/``, where you can replace ``user``
and ``calendar.ics`` by some strings of your choice. Calendars are
automatically created if needed. Please note that **the trailing slash is
important**.

You can now customize your calendar by giving it a nickname and a color. This
is only used by Lightning to identify calendars among others.

If no warning sign appears next to the calendar name, you can now add events
and tasks to your calendar. All events and tasks are stored in the server, they
can be accessed and modified from multiple clients by multiple users at the
same time.

Lightning and Thunderbird cannot access CardDAV servers yet. Also, as of version 
17.0.5 the SOGo Connector addon is not fully functionally and will create extra
address book entries with every sync.

Evolution
~~~~~~~~~

Calendars
+++++++++

First of all, show the calendar page in Evolution by clicking on the calendar
icon at the bottom of the side pane. Then add a new calendar by choosing in the
menu ``File → New → Calendar``.

A new window opens. The calendar ``type`` is ``CalDAV``, and the location is
something like ``http://localhost:5232/user/calendar.ics/``, where you can
replace ``user`` and ``calendar`` by some strings of your choice. Calendars are
automatically created if needed. Please note that **the trailing slash is
important**.

You can fill other attributes like the color and the name, these are only used
for Evolution and are not uploaded.

Click on ``OK``, and your calendar should be ready for use.

Contacts
++++++++

Switch to the contacts page and click ``File → New → Adress book``. In the new
window choose ``WebDAV`` as ``type`` and something like
``http://localhost:5232/user/addressbook.vcf/`` as location. Remember to enter
the correct username.

KOrganizer
~~~~~~~~~~

Calendars
+++++++++
*Tested with 4.8.3, you need one running on Akonadi for Cal/CarDav support.*

The procedure below can also be done trough the sidebar "Calendar Manager".
But to ensure it works for everyone this examples uses the menu-bar.

1. Click ``Settings → Configure KOrganizer``.
2. Click on ``General → Calendars``.
3. Click on ``Add``.
4. Choose ``DAV groupware resource`` (and click ``OK``).
5. Enter your username/passord (and click on ``Next``).
6. Select ``Configure the resource manually`` (and click on ``Finish``).
7. Fill in a Display name.
8. Fill in your Username and Password.
9. Click ``Add``.
10. Choose ``CalDav``.
11. For remote URL enter ``http://myserver:5232/Username/Calendar.ics/``
12. Click ``Fetch``.
13. Select desired calendar.
14. Hit ``OK``.
15. Hit ``OK`` again.
16. Close the Configuration Window (Click ``OK``).
17. Restart Korganizer for the calendar to appear in the "Calendar Manager"
    sidebar (at least with version 4.8.3.)

.. note::
    After you created a calender in a collection you can also use
    ``http://myserver:5232/Username/`` as an URL This will then list all
    available calendars.
    
Contacts
++++++++

You can add a address book analogously to the above instructions, just choose
CardDav and ``http://myserver:5232/Username/AddressBook.vcf/`` in step 10 and
11. Also, if you already have a calendar set up you can add an address book to
its "DAV groupware resource" under Configure-Kontact → Calendar → General →
Calendars → Modify. This way you don't have to enter username and password
twice.

CalendarSync
~~~~~~~~~~~~

CalendarSync can be combined with any Android calendar app and can even
store the calendars in existing Android calendars which are synced by other
sync adapters. Of course it can also create its own calendars.

So, to sync using CalendarSync you will have to:

- start the app,
- press the ``Menu`` button,
- select ``Create WebiCal``,
- choose to start with a guided configuration.

Then enter your URL, Username and Password.
As URL please use ``http(s)://server:port/username/``.

If you can use HTTPS depends on your setup. Please replace ``username``
with the name of your user account.

Press test connection button. If everything signaled as OK then
press search calendars button, select the calendars which you want 
to sync, and press the configure calendar button at the top of 
the display. Your calendars are now configured.

You can then start the first sync by going back to the 
main screen of the app an pressing the ``Process Webicals`` button. Of 
course you can also configure the app at its preferences to sync 
automatically.

ContactSync
~~~~~~~~~~~

ContactSync is designed to sync contacts from and to various sources. It can
also overtake contacts and push them to the server, also if they are only
available on the device (local only contacts).

So to sync your contacts from the Radical server to your Android device:

- start the app
- press the ``Menu`` button,
- select ``Create WebContact``,
- select guided configuration mode.

As URL please use ``http(s)://server:port/username/``.

At the URL you will have to replace ``server:port`` and ``username`` so that it
matches your specific setup. It also depends on your configuration if you can
use HTTPS or if you have to use HTTP.

Press test connection button, if everything signaled as OK then press search
address book button. Select the address books which you want to sync and press
the configure address book button at the top of the display.

You can then start the first sync by going back to the main screen of the app
and pressing the ``Handle WebContacts`` button. Of course you can also
configure the app at its preferences to sync automatically.

CalDAV-Sync
~~~~~~~~~~~

CalDAV-Sync is implemented as sync adapter to integrate seamlessly with 
any calendar app and widget. Therefore you have to access it via 
``Accounts & Sync`` settings after installing it from the Market.

So, to add new calendars to your phone open ``Accounts & Sync`` settings and
tap on ``Add account``, selecting CalDAV as type. In the next view, you have to
switch to Manual Mode. Enter the full CalDAV URL of your Radicale account
(e.g. ``http://example.com:5232/Username/``) and corresponding login data. If
you want to create a new calendar you have to specify its full URL e.g.
``http://example.com:5232/Username/Calendar.ics/``. Please note that **the
trailing slash is important**.

Tap on ``Next`` and the app checks for all available calendars on
your account, listing them in the next view. (Note: CalDAV-Sync
will not only check under the url you entered but also under
``http://example.com:5232/UsernameYouEnteredForLogin/``. This
might cause strange errors.) You can now select calendars you
want to sync and set a local nickname and color for each. Hitting
``Next`` again brings up the last page. Enter your email address
and uncheck ``Sync from server to phone only`` if you want to use
two-way-sync.

.. note::
    CalDAV-Sync officially is in alpha state and two-way-sync is marked as 
    an experimental feature. Though it works fine for me, using two-way-sync 
    is on your own risk!
    
Tap on ``Finish`` and you're done. You're now able to use the new calendars 
in the same way you were using Google calendars before.

CardDAV-Sync
~~~~~~~~~~~~

Set up works like CalDAV-Sync, just use .vcf instead of .ics if you enter the
URL, e.g. ``http://example.com:5232/Username/AddressBook.vcf/``.

DAVdroid
~~~~~~~~

`DAVdroid <http://davdroid.bitfire.at>`_ is a free and open-source CalDAV/CardDAV
client that is available in Play Store for a small fee or in FDroid for free.

To make it working with Radicale, just add a new DAVdroid account and enter
``https://example.com/radicale/user/`` as base URL (assuming that your Radicale
runs at ``https://example.com/radicale/``; don't forget to set base_prefix correctly).

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

|

InfCloud, CalDavZAP & CardDavMATE
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

| Because settings are the same for ``InfCloud``, ``CalDavZAP`` and ``CardDavMATE``
| only *InfCloud* is used in description below.

Radicale configuration
++++++++++++++++++++++

Add/Modify the following section in Radicale main configuration file:

.. code-block:: ini

    # Additional HTTP headers
    [headers]
    Access-Control-Allow-Origin = *
    Access-Control-Allow-Methods = GET, POST, OPTIONS, PROPFIND, PROPPATCH, REPORT, PUT, MOVE, DELETE, LOCK, UNLOCK
    Access-Control-Allow-Headers = User-Agent, Authorization, Content-type, Depth, If-match, If-None-Match, Lock-Token, Timeout, Destination, Overwrite, X-client, X-Requested-With
    Access-Control-Expose-Headers = Etag

``InfCloud`` needs read access for ``everybody`` (including anonymous users) on Radicale's root directory.
If using Radicales rights management add the following section to rights file:

.. code-block:: ini

    # Allow caldavzap, carddavmate and infcloud to work
    [infcloud]
    user: .*
    collection: /
    permission: r

Additional you need to change ``[owner-write]`` section to use the same syntax for collection as shown in ``[public]`` section.

.. code-block:: ini

    # Give write access to owners
    [owner-write]
    user: .+
    # collection: ^%(login)s/.+$    # DOES NOT WORK
    collection: ^%(login)s(/.+)?$
    permission: rw

InfCloud configuration
++++++++++++++++++++++

Inside ``InfCloud`` configuration file ``config.js`` you need to set ``globalNetworkCheckSettings`` like following example:

.. code-block:: JavaScript

    // href: 
    // put in here your protocol, host and port where Radicale is listening
    // additionalResources:
    // put in here a comma separated list of collections you want additionally look at.
    // Don't forget '' around each collections name
    var globalNetworkCheckSettings={
        href: 'https://host.example.com:5232/',
        hrefLabel: null,
        crossDomain: null,
        additionalResources: ['public'],
        forceReadOnly: null,
        withCredentials: false,
        showHeader: true,
        settingsAccount: true,
        syncInterval: 60000,
        timeOut: 30000,
        lockTimeOut: 10000,
        delegation: false,
        ignoreAlarms: false,
        backgroundCalendars: []
    }

.. note::
    ``InfCloud``, ``CardDavMATE`` and ``CalDavZAP`` cannot create calendars and/or address books. **They need to be created before first login.**
    Each user needs to have minimum of one calendar and/or one adressbook even if only using shared addresses and/or calendars.
    Client will not login, if the user collections don't exists.

| You can easily create them by directly calling the URL's from your browser:
|   ``http(s)://host.example.com:5232/user/calendar.ics/``
|   ``http(s)://host.example.com:5232/user/addresses.vcf/``

| Replace "http(s)" with the correct protocol, "host.example.com:5232" with you host:port where Radicale is running,
| "user" with the correct login name or the shared resource name i.e. 'public',
| "calendar.ics" and "addresses.vcf" with the collection names you want to use
| and **do NOT forget the '/' at line end**.

.. note::
    | If using self-signed certificates you need to do the following steps before using ``InfCloud, CardDavMATE`` or ``CalDavZAP``.
    | With your browser call one of the above URLs.
    | Your browser warn you that you are trying to access an ``Insecure`` site.
    | Download and accept the certificate offered by the Radicale server.
    | After installing and accepting it you should restart your browser.

|

iPhone & iPad
~~~~~~~~~~~~~

Calendars
+++++++++

For iOS devices, the setup is fairly straightforward but there are a few settings
that are critical for proper operation.

1. From the Home screen, open ``Settings``
2. Select ``Mail, Contacts, Calendars``
3. Select ``Add Account…`` →  ``Other`` →  ``Add CalDAV Account``
4. Enter the server URL here, including ``https``, the port, and the user/calendar
   path, ex: ``https://myserver.domain.com:3000/bob/birthdays.ics/`` (please note
   that **the trailing slash is important**)
5. Enter your username and password as defined in your server config
6. Enter a good description of the calendar in the ``Description`` field.
   Otherwise it will put the whole servername in the field.
7. Now go back to the ``Mail, Contacts, Calendars`` screen and scroll down to the
   ``Calendars`` section. You must change the ``Sync`` option to sync ``All events``
   otherwise new events won't show up on your iOS devices!

.. note::
   Everything should be working now so test creating events and make sure they
   stay created.  If you create events on your iOS device and they disappear
   after the fetch period, you probably forgot to change the sync setting in
   step 7. Likewise, if you create events on another device and they don't
   appear on your iPad of iPhone, then make sure your sync settings are correct

.. warning::
   In iOS 5.x, please check twice that the ``Sync all entries`` option is
   activated, otherwise some events may not be shown in your calendar.

Contacts
++++++++

In Contacts on iOS 6:

1.  From the Home screen, open ``Settings``
2.  Select ``Mail, Contacts, Calendars``
3.  Select ``Add Account…`` →  ``Other`` →  ``Add CardDAV Account``
4.  As ``Server`` use the Radicale server URL with port, for example ``localhost:5232``
5.  Add any ``User name`` you like (if you didn't configure authentication)
6.  Add any ``Password`` you like (again, if you didn't configure authentication)
7.  Change the ``Description`` to something more readable (optional)
8.  Tap ``Next``
9.  An alert showing `Cannot Connect Using SSL` will pop up as we haven't configured
    SSL yet, ``Continue`` for now
10. Back on the ``Mail, Contacts, Calendars`` screen you scroll to the ``Contacts`` section,
    select the Radicale server as ``Default Account`` when you want to save new contacts to
    the Radicale server
11. Exit to the Home screen and open ``Contacts``, tap ``Groups``, you should see the
    Radicale server

.. note::
   You'll need version 0.8.1 or up for this to work. Earlier versions will forget your new
   settings after a reboot.

OS X
~~~~

.. note::
   This description assumes you do not have any authentication or encryption
   configured. If you want to use iCal with authentication or encryption, you
   just have to fill in the corresponding fields in your calendar's configuration.

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
   (this would be the case if you start an unconfigured Radicale on your local
   machine)

Click ``Create``. The wizard will now tell you, that no encryption is in place
(``Unsecured Connection``). This is expected and will change if you configure
Radicale to use SSL. Click ``Continue``.

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

In Contacts 7 (previously known as AddressBook):

1. Open the ``Preferences`` dialog and select the ``Accounts`` tab.
2. Click the ``+`` button at the lower left to open the account creation wizard.
3. As ``Account type`` select ``CardDAV``.
4. Add any ``User name`` you like.
5. The ``Password`` field can be left empty (if we didn't configure
   authentication).
6. As ``Server address`` use ``domain:port``, for example ``localhost:5232``
   (this would be the case if you start an unconfigured Radicale server on your local
   machine).
7. Click ``Create``. Contacts will complain about an `Unsecured Connection` if you
   don't have SSL enabled. Click ``Create`` again.
8. You might want to change the ``Description`` of the newly added account to
   something more readable. (optional)
9. Switch to the ``General`` tab in the preferences and select the Radicale server
   as ``Default Account`` at the bottom of the screen. It probably shows up as
   ```domain:port`` or the name you choose if you changed the description. Newly
   added contacts are added to the default account and by default this will be the
   local `On My Mac` account.

.. note::
   You'll need version 0.8.1 or up for this to work. Earlier versions can read CardDAV
   contacts but can't add new contacts.

syncEvolution
~~~~~~~~~~~~~

You can find more information about syncEvolution and Radicale on the
`syncEvolution wiki page
<https://syncevolution.org/wiki/synchronizing-radicale>`_.

Nokia / Microsoft Windows Phones
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Go to "Settings" > "email+accounts"
2. Click "add an account" > "iCloud"
3. Enter random email address (e.g. "foo@bar" and "qwerty") > "sign in"
4. A new account "iCloud" with the given email address appears on the list.
   The status is "Not up to date". Click the account.
5. An error message is given. Click "close".
6. Enter new and "real" values to the account setting fields:

   - "Account name": This name appears on the calendar etc.
     Examples: "Home", "Word", "Sauna reservation"
   - "Email address": Not used
   - "Sync contacts and calendar": Select the sync interval
   - "Content to sync": Uncheck "Contacts", check "Calendar"
   - "Your name": Not used
   - "Username": Username to your Radicale server
   - "Password": Password to your Radicale server
   - Click "advanced settings"
   - "Calendar server (CalDAV)": Enter the full path to the calendar .ics file.
     Don't forget the trailing slash.
     Example: `https://my.server.fi:5232/myusername/calendarname.ics/`

Don't forget to add your CA to the phone if you're using a self-signed certificate
on your Radicale. Make the CA downloadable to Internet Explorer. The correct
certificate format is X509 (with .cer file extension).

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
   This section is following the latest stable version changes. Please look at
   the default configuration file included in your package if you have an older
   version of Radicale.

The server configuration can be modified in ``/etc/radicale/config`` or in
``~/.config/radicale/config``. You can use the ``--config`` parameter in the
command line to choose a specific path. You can also set the
``RADICALE_CONFIG`` environment variable to a path of your choice. Here is the
default configuration file, with the main parameters:

.. code-block:: ini

  [server]

  # CalDAV server hostnames separated by a comma
  # IPv4 syntax: address:port
  # IPv6 syntax: [address]:port
  # For example: 0.0.0.0:9999, [::]:9999
  # IPv6 adresses are configured to only allow IPv6 connections
  #hosts = 0.0.0.0:5232

  # Daemon flag
  #daemon = False

  # File storing the PID in daemon mode
  #pid =

  # SSL flag, enable HTTPS protocol
  #ssl = False

  # SSL certificate path
  #certificate = /etc/apache2/ssl/server.crt

  # SSL private key
  #key = /etc/apache2/ssl/server.key

  # SSL Protocol used. See python's ssl module for available values
  #protocol = PROTOCOL_SSLv23

  # Ciphers available. See python's ssl module for available ciphers
  #ciphers =

  # Reverse DNS to resolve client address in logs
  #dns_lookup = True

  # Root URL of Radicale (starting and ending with a slash)
  #base_prefix = /

  # Possibility to allow URLs cleaned by a HTTP server, without the base_prefix
  #can_skip_base_prefix = False

  # Message displayed in the client when a password is needed
  #realm = Radicale - Password Required


  [encoding]

  # Encoding for responding requests
  #request = utf-8

  # Encoding for storing local collections
  #stock = utf-8


  [well-known]

  # Path where /.well-known/caldav/ is redirected
  #caldav = '/%(user)s/caldav/'

  # Path where /.well-known/carddav/ is redirected
  #carddav = '/%(user)s/carddav/'


  [auth]

  # Authentication method
  # Value: None | htpasswd | IMAP | LDAP | PAM | courier | http | remote_user | custom
  #type = None

  # Custom authentication handler
  #custom_handler =

  # Htpasswd filename
  #htpasswd_filename = /etc/radicale/users

  # Htpasswd encryption method
  # Value: plain | sha1 | ssha | crypt | bcrypt | md5
  #htpasswd_encryption = crypt

  # LDAP server URL, with protocol and port
  #ldap_url = ldap://localhost:389/

  # LDAP base path
  #ldap_base = ou=users,dc=example,dc=com

  # LDAP login attribute
  #ldap_attribute = uid

  # LDAP filter string
  # placed as X in a query of the form (&(...)X)
  # example: (objectCategory=Person)(objectClass=User)(memberOf=cn=calenderusers,ou=users,dc=example,dc=org)
  # leave empty if no additional filter is needed
  #ldap_filter =

  # LDAP dn for initial login, used if LDAP server does not allow anonymous searches
  # Leave empty if searches are anonymous
  #ldap_binddn =

  # LDAP password for initial login, used with ldap_binddn
  #ldap_password =

  # LDAP scope of the search
  #ldap_scope = OneLevel

  # IMAP Configuration
  #imap_hostname = localhost
  #imap_port = 143
  #imap_ssl = False

  # PAM group user should be member of
  #pam_group_membership =

  # Path to the Courier Authdaemon socket
  #courier_socket =

  # HTTP authentication request URL endpoint
  #http_url =
  # POST parameter to use for username
  #http_user_parameter =
  # POST parameter to use for password
  #http_password_parameter =


  [git]

  # Git default options
  #committer = Radicale <radicale@example.com>


  [rights]

  # Rights backend
  # Value: None | authenticated | owner_only | owner_write | from_file | custom
  #type = None

  # Custom rights handler
  #custom_handler =

  # File for rights management from_file
  #file = ~/.config/radicale/rights


  [storage]

  # Storage backend
  # -------
  # WARNING: ONLY "filesystem" IS DOCUMENTED AND TESTED,
  #          OTHER BACKENDS ARE NOT READY FOR PRODUCTION.
  # -------
  # Value: filesystem | multifilesystem | database | custom
  #type = filesystem

  # Custom storage handler
  #custom_handler =

  # Folder for storing local collections, created if not present
  #filesystem_folder = ~/.config/radicale/collections

  # Database URL for SQLAlchemy
  # dialect+driver://user:password@host/dbname[?key=value..]
  # For example: sqlite:///var/db/radicale.db, postgresql://user:password@localhost/radicale
  # See http://docs.sqlalchemy.org/en/rel_0_8/core/engines.html#sqlalchemy.create_engine
  #database_url =


  [logging]

  # Logging configuration file
  # If no config is given, simple information is printed on the standard output
  # For more information about the syntax of the configuration file, see:
  # http://docs.python.org/library/logging.config.html
  #config = /etc/radicale/logging
  # Set the default logging level to debug
  #debug = False
  # Store all environment variables (including those set in the shell)
  #full_environment = False


  [headers]

  # Additional HTTP headers
  #Access-Control-Allow-Origin = *

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
<https://pypi.python.org/pypi/flup/>`_ to wrap Radicale into a CGI,
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
   The ``hosts``, ``daemon``, ``pid``, ``ssl``, ``certificate``, ``key``,
   ``protocol`` and ``ciphers`` keys of the ``[server]`` part of the
   configuration are ignored.

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

Deactivate any rights and  module in Radicale and use your favourite Apache
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


Authentication
--------------

Authentication is possible through:

- Courier-Authdaemon socket
- htpasswd file, including list of plain user/password couples
- HTTP, checking status code of a POST request
- IMAP
- LDAP
- PAM
- Remote user given by HTTP server

Check the ``[auth]`` section of your configuration file to know the different
options offered by these authentication modules.

Some authentication methods need additional modules, see `Python Versions and
OS Support`_ for further information.

You can also write and use a custom module handle authentication if you use a
different technology.

Please note that these modules have not been verified by security experts. If
you need a really secure way to handle authentication, you should put Radicale
behind a real HTTP server and use its authentication and rights management
methods.


Rights Management
-----------------

You can set read and write rights for collections according to the authenticated
user and the owner of the collection.

The *owner of a collection* is determined by the URL of the collection. For
example, ``http://my.server.com:5232/anna/calendar.ics/`` is owned by the user
called ``anna``.

The *authenticated user* is the login used for authentication.

5 different configurations are available, you can choose the one you want in
your configuration file. You can also write and use a custom module handle
rights management if you need a specific pattern.

None
~~~~

Everybody (including anonymous users) has read and write access to all collections.

Authenticated
~~~~~~~~~~~~~

An authenticated users has read and write access to all collections, anonymous
users have no access to these collections.

Owner Only
~~~~~~~~~~

Only owners have read and write access to their own collections. The other
users, authenticated or anonymous, have no access to these collections.

Owner Write
~~~~~~~~~~~

Authenticated users have read access to all collections, but only owners have
write access to their own collections. Anonymous users have no access to
collections.

From File
~~~~~~~~~

Rights are based on a regex-based file whose name is specified in the config
(section "right", key "file").

Authentication login is matched against the "user" key, and collection's path
is matched against the "collection" key. You can use Python's ConfigParser
interpolation values %(login)s and %(path)s. You can also get groups from the
user regex in the collection with {0}, {1}, etc.

For example, for the "user" key, ".+" means "authenticated user" and ".*"
means "anybody" (including anonymous users).

Section names are only used for naming the rule.

Leading or ending slashes are trimmed from collection's path.

Example:

.. code-block:: ini

  # This means all users starting with "admin" may read any collection
  [admin]
  user: ^admin.*$
  collection: .*
  permission: r

  # This means all users may read and write any collection starting with public.
  # We do so by just not testing against the user string.
  [public]
  user: .*
  collection: ^public(/.+)?$
  permission: rw

  # A little more complex: give read access to users from a domain for all
  # collections of all the users (ie. user@domain.tld can read domain/\*).
  [domain-wide-access]
  user: ^.+@(.+)\..+$
  collection: ^{0}/.+$
  permission: r

  # Allow authenticated user to read all collections
  [allow-everyone-read]
  user: .+
  collection: .*
  permission: r

  # Give write access to owners
  [owner-write]
  user: .+
  collection: ^%(login)s/.+$
  permission: w


Git Support
-----------

.. note::
   If the project doesn't comply with the requirements to use Git, Radicale will still work.
   Your collections will run fine but without the versionning system.

Git is now automatically supported on Radicale. It depends on `dulwich <https://github.com/jelmer/dulwich>`_.


Configure Radicale
~~~~~~~~~~~~~~~~~~

Radicale automatically detects the *.git* folder in the path you configured for
the filesystem_folder variable in the ``[storage]`` section of your configuration file.
Make sure a repository is created at this location or create one (using *git init
.* for instance) else it won't work.

To summarize : 

- Configure your Git installation
- Get Radicale and dulwich
- Create the repository where your collections are stored
- Run Radicale and it should work

How it works
~~~~~~~~~~~~

Radicale will automatically commit any changes on your collections. It
will use your git config to find parameters such as the committer and that's all.


Issues
~~~~~~

A dulwich project ported on Python 3 exists but it seems that it doesn't follow the
current api (committer is mandatory and not retrieved from the git config by
default). Until this problem isn't fixed, the Git support for Radicale on
Python 3 will not be ensured.


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

Additional ``md5`` and ``bcrypt`` methods are available when the ``passlib``
module is installed.

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

The PAM authentication module relies on `the python-pam module
<https://pypi.python.org/pypi/python-pam/>`_.

Bear in mind that on Linux systems, if you're authenticating against PAM
files (i.e. ``/etc/shadow``), the user running Radicale must have the right
permissions. For instance, you might want to add the ``radicale`` user
to the ``shadow`` group.

HTTP Authentication
-------------------

The HTTP authentication module relies on `the requests module
<http://docs.python-requests.org/en/latest/>`_.

Daemon Mode
-----------

The daemon mode relies on forks, and thus only works on Unix-like OSes
(incuding Linux, OS X, BSD).
