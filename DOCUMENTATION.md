# A Simple Calendar and Contact Server

### Presentation

The Radicale Project is a complete CalDAV (calendar) and CardDAV
(contact) server solution.

Calendars and address books are available for both local and remote
access, possibly limited through authentication policies. They can be
viewed and edited by calendar and contact clients on mobile phones or
computers.

### Technical Description

Radicale aims to be a light solution, easy to use, easy to install, easy
to configure. As a consequence, it requires few software dependencies
and is pre-configured to work out-of-the-box.

Radicale runs on most of the UNIX-like platforms (Linux, \*BSD, MacOS X)
and Windows. It is free and open-source software, written in Python,
released under GPL version 3.

### Main Features

  - Shares calendars through CalDAV, WebDAV and HTTP
  - Shares contacts through CardDAV, WebDAV and HTTP
  - Supports events, todos, journal entries and business cards
  - Works out-of-the-box, no installation nor configuration required
  - Warns users on concurrent editing
  - Limits access by authentication
  - Secures connections

### Supported Clients

Radicale supports the latest versions of [many CalDAV and CardDAV
clients](#documentation/user-documentation/installation/caldav-and-carddav-clients).

# Documentation

### User documentation

This document describes how to install and configure the server.

  - [User documentation](#documentation/user-documentation)

### Project description

This document defines the main goals of the Radicale Project, what it
covers and what it does not.

  - [Project description](#documentation/project-description)

### Technical choices

This document describes the global technical choices of the Radicale
Project and the global architectures of its different parts.

  - [Technical choices](#documentation/technical-choices)

## User Documentation

### Installation

#### Dependencies

Radicale is written in pure Python and does not depend on any library.
It is known to work on Python 2.6, 2.7, 3.1, 3.2, 3.3, 3.4 and PyPy \>
1.9. The dependencies are optional, as they are only needed for various
authentication methods[\[1\]](#footnotes//1).

Linux and MacOS users certainly have Python already installed. For
Windows users, please install Python[\[2\]](#footnotes//2) thanks to the adequate
installer.

#### Radicale

Radicale can be freely downloaded on the [project website, download
section](#download). Just get the file and unzip
it in a folder of your choice.

#### CalDAV and CardDAV Clients

At this time Radicale has been tested and works fine with the latest
version of:

  - [Mozilla
    Lightning](http://www.mozilla.org/projects/calendar/lightning/)
  - [GNOME Evolution](http://projects.gnome.org/evolution/)
  - [KDE KOrganizer](http://userbase.kde.org/KOrganizer/)
  - [aCal](http://wiki.acal.me/wiki/Main_Page),
    [ContactSync](https://play.google.com/store/apps/details?id=com.vcard.android.free),
    [CalendarSync](https://play.google.com/store/apps/details?id=com.icalparse.free),
    [CalDAV-Sync](https://play.google.com/store/apps/details?id=org.dmfs.caldav.lib)
    [CardDAV-Sync](https://play.google.com/store/apps/details?id=org.dmfs.carddav.Sync)
    and [DAVdroid](http://davdroid.bitfire.at) for [Google
    Android](http://www.android.com/)
  - [InfCloud](http://www.inf-it.com/open-source/clients/infcloud/),
    [CalDavZAP](http://www.inf-it.com/open-source/clients/caldavzap/),
    [CardDavMATE](http://www.inf-it.com/open-source/clients/carddavmate/)
  - [Apple iPhone](http://www.apple.com/iphone/)
  - [Apple Calendar](http://www.apple.com/macosx/apps/#calendar)
  - [Apple Contacts](http://www.apple.com/macosx/apps/#contacts)
  - [syncEvolution](https://syncevolution.org/)

More clients will be supported in the future. However, it may work with
any calendar or contact client which implements CalDAV or CardDAV
specifications too (luck is highly recommended).

### Simple Usage

#### Starting the Server

To start Radicale CalDAV server, you have to launch the file called
`radicale.py` located in the root folder of the software package.

#### Starting the Client

##### Lightning

After starting Lightning, click on `File` and `New Calendar`. Upcoming
window asks you about your calendar storage. Chose a calendar `On the
Network`, otherwise Lightning will use its own file system storage
instead of Radicale's one and your calendar won't be remotely
accessible.

Next window asks you to provide information about remote calendar
access. Protocol used by Radicale is `CalDAV`. A standard location for a
basic use of a Radicale calendar is
`http://localhost:5232/user/calendar.ics/`, where you can replace `user`
and `calendar.ics` by some strings of your choice. Calendars are
automatically created if needed. Please note that **the trailing slash
is important**.

You can now customize your calendar by giving it a nickname and a color.
This is only used by Lightning to identify calendars among others.

If no warning sign appears next to the calendar name, you can now add
events and tasks to your calendar. All events and tasks are stored in
the server, they can be accessed and modified from multiple clients by
multiple users at the same time.

Lightning and Thunderbird cannot access CardDAV servers yet. Also, as of
version 17.0.5 the SOGo Connector addon is not fully functionally and
will create extra address book entries with every sync.

##### Evolution

###### Calendars

First of all, show the calendar page in Evolution by clicking on the
calendar icon at the bottom of the side pane. Then add a new calendar by
choosing in the menu `File → New → Calendar`.

A new window opens. The calendar `type` is `CalDAV`, and the location is
something like `http://localhost:5232/user/calendar.ics/`, where you can
replace `user` and `calendar` by some strings of your choice. Calendars
are automatically created if needed. Please note that **the trailing
slash is important**.

You can fill other attributes like the color and the name, these are
only used for Evolution and are not uploaded.

Click on `OK`, and your calendar should be ready for use.

###### Contacts

Switch to the contacts page and click `File → New → Adress book`. In the
new window choose `WebDAV` as `type` and something like
`http://localhost:5232/user/addressbook.vcf/` as location. Remember to
enter the correct username.

##### KOrganizer

###### Calendars

*Tested with 4.8.3, you need one running on Akonadi for Cal/CarDav
support.*

The procedure below can also be done trough the sidebar "Calendar
Manager". But to ensure it works for everyone this examples uses the
menu-bar.

1.  Click `Settings → Configure KOrganizer`.
2.  Click on `General → Calendars`.
3.  Click on `Add`.
4.  Choose `DAV groupware resource` (and click `OK`).
5.  Enter your username/passord (and click on `Next`).
6.  Select `Configure the resource manually` (and click on `Finish`).
7.  Fill in a Display name.
8.  Fill in your Username and Password.
9.  Click `Add`.
10. Choose `CalDav`.
11. For remote URL enter `http://myserver:5232/Username/Calendar.ics/`
12. Click `Fetch`.
13. Select desired calendar.
14. Hit `OK`.
15. Hit `OK` again.
16. Close the Configuration Window (Click `OK`).
17. Restart Korganizer for the calendar to appear in the "Calendar
    Manager" sidebar (at least with version 4.8.3.)

> **Note**
>
> After you created a calender in a collection you can also use
> `http://myserver:5232/Username/` as an URL This will then list all
> available calendars.


###### Contacts

You can add a address book analogously to the above instructions, just
choose CardDav and `http://myserver:5232/Username/AddressBook.vcf/` in
step 10 and 11. Also, if you already have a calendar set up you can add
an address book to its "DAV groupware resource" under Configure-Kontact
→ Calendar → General → Calendars → Modify. This way you don't have to
enter username and password twice.

##### CalendarSync

CalendarSync can be combined with any Android calendar app and can even
store the calendars in existing Android calendars which are synced by
other sync adapters. Of course it can also create its own calendars.

So, to sync using CalendarSync you will have to:

  - start the app,
  - press the `Menu` button,
  - select `Create WebiCal`,
  - choose to start with a guided configuration.

Then enter your URL, Username and Password. As URL please use
`http(s)://server:port/username/`.

If you can use HTTPS depends on your setup. Please replace `username`
with the name of your user account.

Press test connection button. If everything signaled as OK then press
search calendars button, select the calendars which you want to sync,
and press the configure calendar button at the top of the display. Your
calendars are now configured.

You can then start the first sync by going back to the main screen of
the app an pressing the `Process Webicals` button. Of course you can
also configure the app at its preferences to sync automatically.

##### ContactSync

ContactSync is designed to sync contacts from and to various sources. It
can also overtake contacts and push them to the server, also if they are
only available on the device (local only contacts).

So to sync your contacts from the Radical server to your Android device:

  - start the app
  - press the `Menu` button,
  - select `Create WebContact`,
  - select guided configuration mode.

As URL please use `http(s)://server:port/username/`.

At the URL you will have to replace `server:port` and `username` so that
it matches your specific setup. It also depends on your configuration if
you can use HTTPS or if you have to use HTTP.

Press test connection button, if everything signaled as OK then press
search address book button. Select the address books which you want to
sync and press the configure address book button at the top of the
display.

You can then start the first sync by going back to the main screen of
the app and pressing the `Handle WebContacts` button. Of course you can
also configure the app at its preferences to sync automatically.

##### CalDAV-Sync

CalDAV-Sync is implemented as sync adapter to integrate seamlessly with
any calendar app and widget. Therefore you have to access it via
`Accounts & Sync` settings after installing it from the Market.

So, to add new calendars to your phone open `Accounts & Sync` settings
and tap on `Add account`, selecting CalDAV as type. In the next view,
you have to switch to Manual Mode. Enter the full CalDAV URL of your
Radicale account (e.g. `http://example.com:5232/Username/`) and
corresponding login data. If you want to create a new calendar you have
to specify its full URL e.g.
`http://example.com:5232/Username/Calendar.ics/`. Please note that **the
trailing slash is important**.

Tap on `Next` and the app checks for all available calendars on your
account, listing them in the next view. (Note: CalDAV-Sync will not only
check under the url you entered but also under
`http://example.com:5232/UsernameYouEnteredForLogin/`. This might cause
strange errors.) You can now select calendars you want to sync and set a
local nickname and color for each. Hitting `Next` again brings up the
last page. Enter your email address and uncheck `Sync from server to
phone only` if you want to use two-way-sync.

> **Note**
>
> CalDAV-Sync officially is in alpha state and two-way-sync is marked as
> an experimental feature. Though it works fine for me, using two-way-sync
> is on your own risk\!


Tap on `Finish` and you're done. You're now able to use the new
calendars in the same way you were using Google calendars before.

##### CardDAV-Sync

Set up works like CalDAV-Sync, just use .vcf instead of .ics if you
enter the URL, e.g. `http://example.com:5232/Username/AddressBook.vcf/`.

##### DAVdroid

[DAVdroid](http://davdroid.bitfire.at) is a free and open-source
CalDAV/CardDAV client that is available in Play Store for a small fee or
in FDroid for free.

To make it working with Radicale, just add a new DAVdroid account and
enter `https://example.com/radicale/user/` as base URL (assuming that
your Radicale runs at `https://example.com/radicale/`; don't forget to
set base\_prefix correctly).

##### aCal

aCal is a CalDAV client for Android. It comes with its own calendar
application and does not integrate in the Android calendar. It is a
"CalDAV only" calendar, i.e. it only works in combination with a CalDAV
server. It can connect to several calendars on the server and will
display them all in one calendar. It works nice with Radicale.

To configure aCal, start aCal, go to the `Settings` screen, select
`Server`, then `Add server`. Choose `Manual Configuration` and select
`Advanced` (bottom of the screen). Then enter the host name of your
server, check `Active`, enter your user name and password. The `Simple
Domain` of your server is the domain part of your fully qualified host
name (e.g. if your server is `myserver.mydomain.org`, choose
`mydomain.org`).

As `Simple Path` you need to specify `/<user>` where user is the user
you use to connect to Radicale. `Server Name` is the fully qualified
name of your server machine (`myserver.mydomain.org`). The `Server Path`
is `/<user>/`.

For `Authentication Type` you need to specify the method you chose for
Radicale. Check `Use SSL` if your Radicale is configured to use SSL.

As the last thing you need to specify the port Radicale listens to. When
your server is configured you can go back to the first `Settings`
screen, and select `Calendars and Addressbooks`. You should find all the
calendars that are available to your user on the Radicale server. You
can then configure each of them (display colour, notifications, etc.).

##### InfCloud, CalDavZAP & CardDavMATE

Because settings are the same for `InfCloud`, `CalDavZAP` and
`CardDavMATE`  
only *InfCloud* is used in description below.

###### Radicale configuration

Add/Modify the following section in Radicale main configuration file:

``` ini
# Additional HTTP headers
[headers]
Access-Control-Allow-Origin = *
Access-Control-Allow-Methods = GET, POST, OPTIONS, PROPFIND, PROPPATCH, REPORT, PUT, MOVE, DELETE, LOCK, UNLOCK
Access-Control-Allow-Headers = Authorization, Content-type, Depth, Destination, If-match, If-None-Match, Lock-Token, Overwrite, Prefer, Timeout, User-Agent, X-Client, X-Requested-With
Access-Control-Expose-Headers = Etag
```

`InfCloud` needs read access for `everybody` (including anonymous users)
on Radicale's root directory. If using Radicales rights management add
the following section to rights file:

``` ini
# Allow caldavzap, carddavmate and infcloud to work
[infcloud]
user: .*
collection: /
permission: r
```

Additional you need to change `[owner-write]` section to use the same
syntax for collection as shown in `[public]` section.

``` ini
# Give write access to owners
[owner-write]
user: .+
# collection: ^%(login)s/.+$    # DOES NOT WORK
collection: ^%(login)s(/.+)?$
permission: rw
```

###### InfCloud configuration

Inside `InfCloud` configuration file `config.js` you need to set
`globalNetworkCheckSettings` like following example:

``` JavaScript
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
```

> **Note**
>
> `InfCloud`, `CardDavMATE` and `CalDavZAP` cannot create calendars and/or
> address books. **They need to be created before first login.** Each user
> needs to have minimum of one calendar and/or one adressbook even if only
> using shared addresses and/or calendars. Client will not login, if the
> user collections don't exists.


You can easily create them by directly calling the URL's from your
browser:  
  `http(s)://host.example.com:5232/user/calendar.ics/`  
  `http(s)://host.example.com:5232/user/addresses.vcf/`

Replace "http(s)" with the correct protocol, "host.example.com:5232"
with you host:port where Radicale is running,  
"user" with the correct login name or the shared resource name i.e.
'public',  
"calendar.ics" and "addresses.vcf" with the collection names you want to
use  
and **do NOT forget the '/' at line end**.

> **Note**
>
> If using self-signed certificates you need to do the following steps
> before using `InfCloud, CardDavMATE` or `CalDavZAP`.  
> With your browser
> call one of the above URLs.  
> Your browser warn you that you are trying
> to access an `Insecure` site.  
> Download and accept the certificate
> offered by the Radicale server.  
> After installing and accepting it you
> should restart your browser.


##### iPhone & iPad

###### Calendars

For iOS devices, the setup is fairly straightforward but there are a few
settings that are critical for proper operation.

1.  From the Home screen, open `Settings`
2.  Select `Mail, Contacts, Calendars`
3.  Select `Add Account…` → `Other` → `Add CalDAV Account`
4.  Enter the server URL here, including `https`, the port, and the
    user/calendar path, ex:
    `https://myserver.domain.com:3000/bob/birthdays.ics/` (please note
    that **the trailing slash is important**)
5.  Enter your username and password as defined in your server config
6.  Enter a good description of the calendar in the `Description` field.
    Otherwise it will put the whole servername in the field.
7.  Now go back to the `Mail, Contacts, Calendars` screen and scroll
    down to the `Calendars` section. You must change the `Sync` option
    to sync `All events` otherwise new events won't show up on your iOS
    devices\!

> **Note**
>
> Everything should be working now so test creating events and make sure
> they stay created. If you create events on your iOS device and they
> disappear after the fetch period, you probably forgot to change the sync
> setting in step 7. Likewise, if you create events on another device and
> they don't appear on your iPad of iPhone, then make sure your sync
> settings are correct


> **Warning**
>
> In iOS 5.x, please check twice that the `Sync all entries` option is
> activated, otherwise some events may not be shown in your calendar.


###### Contacts

In Contacts on iOS 6:

1.  From the Home screen, open `Settings`
2.  Select `Mail, Contacts, Calendars`
3.  Select `Add Account…` → `Other` → `Add CardDAV Account`
4.  As `Server` use the Radicale server URL with port, for example
    `localhost:5232`
5.  Add any `User name` you like (if you didn't configure
    authentication)
6.  Add any `Password` you like (again, if you didn't configure
    authentication)
7.  Change the `Description` to something more readable (optional)
8.  Tap `Next`
9.  An alert showing `Cannot Connect Using SSL` will pop up as we haven't configured SSL yet, `Continue`
    for now
10. Back on the `Mail, Contacts, Calendars` screen you scroll to the
    `Contacts` section, select the Radicale server as `Default Account`
    when you want to save new contacts to the Radicale server
11. Exit to the Home screen and open `Contacts`, tap `Groups`, you
    should see the Radicale server

> **Note**
>
> You'll need version 0.8.1 or up for this to work. Earlier versions will
> forget your new settings after a reboot.


##### OS X

> **Note**
>
> This description assumes you do not have any authentication or
> encryption configured. If you want to use iCal with authentication or
> encryption, you just have to fill in the corresponding fields in your
> calendar's configuration.


###### Calendars

In iCal 4.0 or iCal 5.0:

1.  Open the `Preferences` dialog and select the `Accounts` tab
2.  Click the `+` button at the lower left to open the account creation
    wizard
3.  As `Account type` select `CalDAV`
4.  Select any `User name` you like
5.  The `Password` field can be left empty (we did not configure
    authentication)
6.  As `Server address` use `domain:port`, for example `localhost:5232`
    (this would be the case if you start an unconfigured Radicale on
    your local machine)

Click `Create`. The wizard will now tell you, that no encryption is in
place (`Unsecured Connection`). This is expected and will change if you
configure Radicale to use SSL. Click `Continue`.

> **Warning**
>
> In iCal 5.x, please check twice that the `Sync all entries` option is
> activated, otherwise some events may not be shown in your calendar.


The wizard will close, leaving you in the `Account` tab again. The
account is now set-up. You can close the `Preferences` window.

> **Important**
>
> To add a calendar to your shiny new account you have to go to the menu
> and select `File → New Calendar → <your shiny new account>`. A new
> calendar appears in the left panel waiting for you to enter a name.
> 
> This is needed because the behaviour of the big `+` button in the main
> window is confusing as you can't focus an empty account and iCal will
> just add a calendar to another account.


###### Contacts

In Contacts 7 (previously known as AddressBook):

1.  Open the `Preferences` dialog and select the `Accounts` tab.
2.  Click the `+` button at the lower left to open the account creation
    wizard.
3.  As `Account type` select `CardDAV`.
4.  Add any `User name` you like.
5.  The `Password` field can be left empty (if we didn't configure
    authentication).
6.  As `Server address` use `domain:port`, for example `localhost:5232`
    (this would be the case if you start an unconfigured Radicale server
    on your local machine).
7.  Click `Create`. Contacts will complain about an
    `Unsecured Connection` if you don't
    have SSL enabled. Click `Create` again.
8.  You might want to change the `Description` of the newly added
    account to something more readable. (optional)
9.  Switch to the `General` tab in the preferences and select the
    Radicale server as `Default Account` at the bottom of the screen. It
    probably shows up as `` `domain:port `` or the name you choose if
    you changed the description. Newly added contacts are added to the
    default account and by default this will be the local
    `On My Mac` account.

> **Note**
>
> You'll need version 0.8.1 or up for this to work. Earlier versions can
> read CardDAV contacts but can't add new contacts.


##### syncEvolution

You can find more information about syncEvolution and Radicale on the
[syncEvolution wiki
page](https://syncevolution.org/wiki/synchronizing-radicale).

##### Nokia / Microsoft Windows Phones

1.  Go to "Settings" \> "email+accounts"
2.  Click "add an account" \> "iCloud"
3.  Enter random email address (e.g. "<foo@bar>" and "qwerty") \> "sign
    in"
4.  A new account "iCloud" with the given email address appears on the
    list. The status is "Not up to date". Click the account.
5.  An error message is given. Click "close".
6.  Enter new and "real" values to the account setting fields:
      - "Account name": This name appears on the calendar etc. Examples:
        "Home", "Word", "Sauna reservation"
      - "Email address": Not used
      - "Sync contacts and calendar": Select the sync interval
      - "Content to sync": Uncheck "Contacts", check "Calendar"
      - "Your name": Not used
      - "Username": Username to your Radicale server
      - "Password": Password to your Radicale server
      - Click "advanced settings"
      - "Calendar server (CalDAV)": Enter the full path to the calendar
        .ics file. Don't forget the trailing slash. Example:
        `https://my.server.fi:5232/myusername/calendarname.ics/`

Don't forget to add your CA to the phone if you're using a self-signed
certificate on your Radicale. Make the CA downloadable to Internet
Explorer. The correct certificate format is X509 (with .cer file
extension).

### Complex Configuration

> **Note**
>
> This section is written for Linux users, but can be easily adapted for
> Windows and MacOS users.


#### Installing the Server

You can install Radicale thanks to the following command, with superuser
rights:

    python setup.py install

Then, launching the server can be easily done by typing as a normal
user:

    radicale

#### Configuring the Server

##### Main Configuration File

> **Note**
>
> This section is following the latest stable version changes. Please look
> at the default configuration file included in your package if you have
> an older version of Radicale.


The server configuration can be modified in `/etc/radicale/config` or in
`~/.config/radicale/config`. You can use the `--config` parameter in the
command line to choose a specific path. You can also set the
`RADICALE_CONFIG` environment variable to a path of your choice. Here is
the default configuration file, with the main parameters:

``` ini
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
```

This configuration file is read each time the server is launched. If
some values are not given, the default ones are used. If no
configuration file is available, all the default values are used.

##### Logging Configuration File

Radicale uses the default logging facility for Python. The default
configuration prints the information messages to the standard output. It
is possible to print debug messages thanks to:

    radicale --debug

Radicale can also be configured to send the messages to the console,
logging files, syslog, etc. For more information about the syntax of the
configuration file, see:
<http://docs.python.org/library/logging.config.html>. Here is an example
of logging configuration file:

``` ini
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
```

##### Command Line Options

All the options of the `server` part can be changed with command line
options. These options are available by typing:

    radicale --help

#### WSGI, CGI and FastCGI

Radicale comes with a [WSGI](http://wsgi.org/) support, allowing the
software to be used behind any HTTP server supporting WSGI such as
Apache.

Moreover, it is possible to use
[flup](https://pypi.python.org/pypi/flup/) to wrap Radicale into a CGI,
FastCGI, SCGI or AJP application, and therefore use it with Lighttpd,
Nginx or even Tomcat.

##### Apache and mod\_wsgi

To use Radicale with Apache's `mod_wsgi`, you first have to install the
Radicale module in your Python path and write your `.wsgi` file (in
`/var/www` for example):

``` python
import radicale
radicale.log.start()
application = radicale.Application()
```

> **Note**
>
> The `hosts`, `daemon`, `pid`, `ssl`, `certificate`, `key`, `protocol`
> and `ciphers` keys of the `[server]` part of the configuration are
> ignored.


Next you have to create the Apache virtual host (adapt the configuration
to your environment):

``` apache
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
```

> **Warning**
>
> You should use the root of the (sub)domain (`WSGIScriptAlias /`), else
> some CalDAV features may not work.


If you want to use authentication with Apache, you *really* should use
one of the Apache authentication modules, instead of the ones from
Radicale: they're just better.

Deactivate any rights and module in Radicale and use your favourite
Apache authentication backend. You can then restrict the access: allow
the `alice` user to access `/alice/*` URLs, and everything should work
as expected.

Here is one example of Apache configuration file:

``` apache
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

        AllowOverride None
        Require valid-user

        RewriteEngine On
        RewriteCond %{REMOTE_USER}%{PATH_INFO} !^([^/]+/)\1
        RewriteRule .* - [Forbidden]
    </Directory>
</VirtualHost>
```

If you're still convinced that access control is better with Radicale,
you have to add `WSGIPassAuthorization On` in your Apache configuration
files, as explained in [the mod\_wsgi
documentation](http://code.google.com/p/modwsgi/wiki/ConfigurationGuidelines#User_Authentication).

> **Note**
>
> Read-only calendars or address books can also be served by a simple
> Apache HTTP server, as Radicale stores full-text icalendar and vcard
> files with the default configuration.


#### Authentication

Authentication is possible through:

  - Courier-Authdaemon socket
  - htpasswd file, including list of plain user/password couples
  - HTTP, checking status code of a POST request
  - IMAP
  - LDAP
  - PAM
  - Remote user given by HTTP server

Check the `[auth]` section of your configuration file to know the
different options offered by these authentication modules.

Some authentication methods need additional modules, see [Python
Versions and OS Support](#documentation/user-documentation/python-versions-and-os-support) for further
information.

You can also write and use a custom module handle authentication if you
use a different technology.

Please note that these modules have not been verified by security
experts. If you need a really secure way to handle authentication, you
should put Radicale behind a real HTTP server and use its authentication
and rights management methods.

#### Rights Management

You can set read and write rights for collections according to the
authenticated user and the owner of the collection.

The *owner of a collection* is determined by the URL of the collection.
For example, `http://my.server.com:5232/anna/calendar.ics/` is owned by
the user called `anna`.

The *authenticated user* is the login used for authentication.

5 different configurations are available, you can choose the one you
want in your configuration file. You can also write and use a custom
module handle rights management if you need a specific pattern.

##### None

Everybody (including anonymous users) has read and write access to all
collections.

##### Authenticated

An authenticated users has read and write access to all collections,
anonymous users have no access to these collections.

##### Owner Only

Only owners have read and write access to their own collections. The
other users, authenticated or anonymous, have no access to these
collections.

##### Owner Write

Authenticated users have read access to all collections, but only owners
have write access to their own collections. Anonymous users have no
access to collections.

##### From File

Rights are based on a regex-based file whose name is specified in the
config (section "right", key "file").

Authentication login is matched against the "user" key, and collection's
path is matched against the "collection" key. You can use Python's
ConfigParser interpolation values %(login)s and %(path)s. You can also
get groups from the user regex in the collection with {0}, {1}, etc.

For example, for the "user" key, ".+" means "authenticated user" and
".\*" means "anybody" (including anonymous users).

Section names are only used for naming the rule.

Leading or ending slashes are trimmed from collection's path.

Example:

``` ini
# The default path for this kind of files is ~/.config/radicale/rights
# This can be changed in the configuration file
#
# This file gives independant examples to help users write their own
# configuration files. Using these examples together in the same configuration
# file is meaningless.
#
# The first rule matching both user and collection patterns will be returned.

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
# collections of all the users (ie. user@domain.tld can read domain/*).
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
collection: ^%(login)s/.*$
permission: w
```

#### Git Support

> **Note**
>
> If the project doesn't comply with the requirements to use Git, Radicale
> will still work. Your collections will run fine but without the
> versionning system.


Git is now automatically supported on Radicale. It depends on
[dulwich](https://github.com/jelmer/dulwich).

##### Configure Radicale

Radicale automatically detects the *.git* folder in the path you
configured for the filesystem\_folder variable in the `[storage]`
section of your configuration file. Make sure a repository is created at
this location or create one (using *git init .* for instance) else it
won't work.

To summarize :

  - Configure your Git installation
  - Get Radicale and dulwich
  - Create the repository where your collections are stored
  - Run Radicale and it should work

##### How it works

Radicale will automatically commit any changes on your collections. It
will use your git config to find parameters such as the committer and
that's all.

##### Issues

A dulwich project ported on Python 3 exists but it seems that it doesn't
follow the current api (committer is mandatory and not retrieved from
the git config by default). Until this problem isn't fixed, the Git
support for Radicale on Python 3 will not be ensured.

### Python Versions and OS Support

#### TLS Support

Python 2.6 suffered [a bug](http://bugs.python.org/issue5103) causing
huge timeout problems with TLS. The bug is fixed since Python 2.6.6.

IMAP authentication over TLS requires Python 3.2.

Python 2.7 and Python 3.x do not suffer this bug.

#### Crypt Support

With the htpasswd access, many encryption methods are available, and
crypt is the default one in Radicale. Unfortunately, the `crypt` module
is unavailable on Windows, you have to pick another method on this OS.

Additional `md5` and `bcrypt` methods are available when the `passlib`
module is installed.

#### IMAP Authentication

The IMAP authentication module relies on the imaplib module, available
with 2.x versions of Python. However, TLS is only available in Python
3.2. Older versions of Python or a non-modern server who does not
support STARTTLS can only authenticate against `localhost` as passwords
are transmitted in PLAIN. Legacy SSL mode on port 993 is not supported.

#### LDAP Authentication

The LDAP authentication module relies on [the python-ldap
module](http://www.python-ldap.org/), and thus only works with 2.x
versions of Python.

#### PAM Authentication

The PAM authentication module relies on [the python-pam
module](https://pypi.python.org/pypi/python-pam/).

Bear in mind that on Linux systems, if you're authenticating against PAM
files (i.e. `/etc/shadow`), the user running Radicale must have the
right permissions. For instance, you might want to add the `radicale`
user to the `shadow` group.

#### HTTP Authentication

The HTTP authentication module relies on [the requests
module](http://docs.python-requests.org/en/latest/).

#### Daemon Mode

The daemon mode relies on forks, and thus only works on Unix-like OSes
(incuding Linux, OS X, BSD).

## Project Description

### Main Goals

The Radicale Project is a complete calendar and contact storing and
manipulating solution. It can store multiple calendars and multiple
address books.

Calendar and contact manipulation is available from both local and
distant accesses, possibly limited through authentication policies.

### What Radicale Is

#### Calendar and Contact Server

The Radicale Project is mainly a calendar and contact server, giving
local and distant access for reading, creating, modifying and deleting
multiple calendars through simplified CalDAV and CardDAV protocols.

Data can be encrypted by SSL, and their access can be restricted using
different authentication methods.

### What Radicale Is not and will not Be

#### Calendar or Contact User Agent

Radicale is a server, not a client. No interfaces will be created to
work with the server, as it is a really (really really) much more
difficult task[\[3\]](#footnotes//3).

#### Original Calendar or Contact Access Protocol

CalDAV and CardDAV are not perfect protocols. We think that their main
problem is their complexity[\[4\]](#footnotes//4), that is why we decided not to
implement the whole standard but just enough to understand some of its
client-side implementations [\[5\]](#footnotes//5).

CalDAV and CardDAV are the best open standards available and they are
quite widely used by both clients and servers[\[6\]](#footnotes//6). We decided to use
it, and we will not use another one.

## Technical Choices

### Global Technical Choices

#### General Description

The Radicale Project aims to be a light solution, easy to use, easy to
install, easy to configure. As a consequence, it requires few software
dependencies and is pre-configured to work out-of-the-box.

The Radicale Project runs on most of the UNIX-like platforms (Linux,
\*BSD, MacOS X) and Windows. It is free and open-source software.

#### Language

The different parts of the Radicale Project are written in Python. This
is a high-level language, fully object-oriented, available for the main
operating systems and released with a lot of useful libraries.

#### Protocols and Formats

The main protocols and formats fully or partially implemented in the
Radicale Project are described by RFCs:

  - HyperText Transfer Protocol (HTTP)
    [RFC 2616](http://www.faqs.org/rfcs/rfc2616.html "RFC 2616")
  - WebDAV Access Control Protocol (ACL)
    [RFC 3744](http://www.faqs.org/rfcs/rfc3744.html "RFC 3744")
  - Calendaring Extensions to WebDAV (CalDAV)
    [RFC 4791](http://www.faqs.org/rfcs/rfc4791.html "RFC 4791")
  - HTTP Extensions for Web Distributed Authoring and Versioning
    (WebDAV)
    [RFC 4918](http://www.faqs.org/rfcs/rfc4918.html "RFC 4918")
  - Transport Layer Security (TLS)
    [RFC 5246](http://www.faqs.org/rfcs/rfc5246.html "RFC 5246")
  - iCalendar format (iCal)
    [RFC 5545](http://www.faqs.org/rfcs/rfc5545.html "RFC 5545")
  - vCard Format Specification
    [RFC 6350](http://www.faqs.org/rfcs/rfc6350.html "RFC 6350")
  - vCard Extensions to Web Distributed Authoring and Versioning
    (CardDAV)
    [RFC 6352](http://www.faqs.org/rfcs/rfc6352.html "RFC 6352")

> **Note**
>
> CalDAV and CardDAV implementations **require** iCal, vCard, ACL, WebDAV,
> HTTP and TLS. The Radicale Server **does not and will not implement
> correctly** these standards, as explained in the [Development
> Choices](#documentation/technical-choices/global-technical-choices/development-choices) part.


#### Development Choices

Important global development choices have been decided before writing
code. They are very useful to understand why the Radicale Project is
different from other CalDAV and CardDAV servers, and why features are
included or not in the code.

##### Oriented to Calendar and Contact User Agents

Calendar and contact servers work with calendar and contact clients,
using a defined protocol. CalDAV and CardDAV are good protocols,
covering lots of features and use cases, but it is quite hard to
implement fully.

Some calendar servers have been created to follow the CalDAV and CardDAV
RFCs as much as possible: Davical[\[7\]](#footnotes//7), Cosmo[\[8\]](#footnotes//8) and Darwin Calendar
Server[\[9\]](#footnotes//9), for example, are much more respectful of CalDAV and CardDAV
and can be used with a large number of clients. They are very good
choices if you want to develop and test new CalDAV clients, or if you
have a possibly heterogeneous list of user agents.

The Radicale Server does not and **will not** support the CalDAV and
CardDAV standards. It supports the CalDAV and CardDAV implementations of
different clients (Lightning, Evolution, Android, iPhone, iCal, and
more).

##### Simple

The Radicale Server is designed to be simple to install, simple to
configure, simple to use.

The installation is very easy, particularly with Linux: no dependencies,
no superuser rights needed, no configuration required. Launching the
main script out-of-the-box, as a normal user, is often the only step to
have a simple remote calendar and contact access.

Contrary to other servers that are often complicated, require high
privileges or need a strong configuration, the Radicale Server can
(sometimes, if not often) be launched in a couple of minutes, if you
follow the [User
Documentation](#documentation/user-documentation).

##### Lazy

We, Radicale Project developers, are lazy. That is why we have chosen
Python: no more `;` or `{}`[\[10\]](#footnotes//10). This is also why our server is lazy.

The CalDAV RFC defines what must be done, what can be done and what
cannot be done. Many violations of the protocol are totally defined and
behaviours are given in such cases.

The Radicale Server assumes that the clients are perfect and that
protocol violations do not exist. That is why most of the errors in
client requests have undetermined consequences for the lazy server that
can reply good answers, bad answers, or even no answer.

As already mentioned, the Radicale server doesn't fully support the
CalDAV and CardDAV RFCs. For example, nested filters in queries
currently don't work in all cases. Examples of not working queries can
be found in issues [\#120](https://github.com/Kozea/Radicale/issues/120)
and [\#121](https://github.com/Kozea/Radicale/issues/121).

### Architectures

#### General Architecture

Here is a simple overview of the global architecture for reaching a
calendar through network:

<table>
  <thead>
    <tr>
      <th>Part</th>
      <th>Layer</th>
      <th>Protocol or Format</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td rowspan="2">Server</td>
      <td>Calendar/Contact Storage</td>
      <td>iCal/vCard</td>
    </tr>
    <tr>
      <td>Calendar/Contact Server</td>
      <td>CalDAV/CardDAV Server</td>
    </tr>
    <tr>
      <td>Transfer</td>
      <td>Network</td>
      <td>CalDAV/CardDAV (HTTP + TLS)</td>
    </tr>
    <tr>
      <td rowspan="2">Client</td>
      <td>Calendar/Contact Client</td>
      <td>CalDAV/CardDAV Client</td>
    </tr>
    <tr>
      <td>GUI</td>
      <td>Terminal, GTK, etc.</td>
    </tr>
  </tbody>
</table>

The Radicale Project is **only the server part** of this architecture.

#### Code Architecture

The package offers 8 modules.

  - `__main__`  
    The main module provides a simple function called `run`. Its main
    work is to read the configuration from the configuration file and
    from the options given in the command line; then it creates a
    server, according to the configuration.

  - `__init__`  
    This is the core part of the module, with the code for the CalDAV
    server. The server inherits from a HTTP or HTTPS server class, which
    relies on the default HTTP server class given by Python. The code
    managing the different HTTP requests according to the CalDAV
    normalization is written here.

  - `config`  
    This part gives a dict-like access to the server configuration, read
    from the configuration file. The configuration can be altered when
    launching the executable with some command line options.

  - `ical`  
    In this module are written the classes to represent collections and
    items in Radicale. The simple iCalendar and vCard readers and
    writers are included in this file. The readers and writers are small
    and stupid: they do not fully understand the iCalendar format and do
    not know at all what a date is.

  - `xmlutils`  
    The functions defined in this module are mainly called by the CalDAV
    server class to read the XML part of the request, read or alter the
    calendars, and create the XML part of the response. The main part of
    this code relies on ElementTree.

  - `log`  
    The `start` function provided by this module starts a logging
    mechanism based on the default Python logging module. Logging
    options can be stored in a logging configuration file.

  - `acl`  
    This module is a set of Access Control Lists, a set of methods used
    by Radicale to manage rights to access the calendars. When the
    CalDAV server is launched, an Access Control List is chosen in the
    set, according to the configuration. The HTTP requests are then
    filtered to restrict the access using a list of login/password-based
    access controls.

  - `storage`  
    This folder is a set of storage modules able to read and write
    collections. Currently there are three storage modules:
    `filesystem`, storing each collection into one flat plain-text file,
    `multifilesystem`, storing each entries into separates plain-text
    files, and `database`, storing entries in a database. `filesystem`
    is stable and battle-tested, others are experimentals.

<!-- end list -->

# Contribute

### Chat with Us on IRC

Want to say something? Join our IRC room: \#\#kozea on Freenode.

### Report Bugs

Found a bug? Want a new feature? Report a new issue on the `Radicale
bug-tracker`.

### Hack

Interested in hacking? Feel free to clone the `git repository on
Github` if you want to add new features, fix bugs or update
documentation.

# Download

### PyPI

Radicale is [available on PyPI](http://pypi.python.org/pypi/Radicale/).
To install, just type as superuser:

    pip install radicale

### Git Repository

If you want the development version of Radicale, take a look at the `git
repository on GitHub`, or clone it thanks to:

    git clone git://github.com/Kozea/Radicale.git

You can also download [the Radicale package of the git
repository](https://github.com/Kozea/Radicale/tarball/master).

### Source Packages

You can download the Radicale package for each release:

  - [Radicale-1.1.7.tar.gz](https://files.pythonhosted.org/packages/source/R/Radicale/Radicale-1.1.7.tar.gz)
  - [Radicale-1.1.6.tar.gz](https://files.pythonhosted.org/packages/source/R/Radicale/Radicale-1.1.6.tar.gz)
  - [Radicale-1.1.5.tar.gz](https://files.pythonhosted.org/packages/source/R/Radicale/Radicale-1.1.5.tar.gz)
  - [Radicale-1.1.4.tar.gz](https://files.pythonhosted.org/packages/source/R/Radicale/Radicale-1.1.4.tar.gz)
  - [Radicale-1.1.3.tar.gz](https://files.pythonhosted.org/packages/source/R/Radicale/Radicale-1.1.3.tar.gz)
  - [Radicale-1.1.2.tar.gz](https://files.pythonhosted.org/packages/source/R/Radicale/Radicale-1.1.2.tar.gz)
    (47 KiB)
  - [Radicale-1.1.1.tar.gz](http://pypi.python.org/packages/source/R/Radicale/Radicale-1.1.1.tar.gz)
    (47 KiB)
  - [Radicale-1.1.tar.gz](http://pypi.python.org/packages/source/R/Radicale/Radicale-1.1.tar.gz)
    (47 KiB)
  - [Radicale-1.0.1.tar.gz](http://pypi.python.org/packages/source/R/Radicale/Radicale-1.0.1.tar.gz)
    (42 KiB)
  - [Radicale-1.0.tar.gz](http://pypi.python.org/packages/source/R/Radicale/Radicale-1.0.tar.gz)
    (42 KiB)
  - [Radicale-0.10.tar.gz](http://pypi.python.org/packages/source/R/Radicale/Radicale-0.10.tar.gz)
    (42 KiB)
  - [Radicale-0.9.tar.gz](http://pypi.python.org/packages/source/R/Radicale/Radicale-0.9.tar.gz)
    (42 KiB)
  - [Radicale-0.8.tar.gz](http://pypi.python.org/packages/source/R/Radicale/Radicale-0.8.tar.gz)
    (38 KiB)
  - [Radicale-0.7.1.tar.gz](http://pypi.python.org/packages/source/R/Radicale/Radicale-0.7.1.tar.gz)
    (34 KiB)
  - [Radicale-0.7.tar.gz](http://pypi.python.org/packages/source/R/Radicale/Radicale-0.7.tar.gz)
    (34 KiB)
  - [Radicale-0.6.4.tar.gz](http://pypi.python.org/packages/source/R/Radicale/Radicale-0.6.4.tar.gz)
    (31 KiB)
  - [Radicale-0.6.3.tar.gz](http://pypi.python.org/packages/source/R/Radicale/Radicale-0.6.3.tar.gz)
    (31 KiB)
  - [Radicale-0.6.2.tar.gz](http://pypi.python.org/packages/source/R/Radicale/Radicale-0.6.2.tar.gz)
    (30 KiB)
  - [Radicale-0.6.1.tar.gz](http://pypi.python.org/packages/source/R/Radicale/Radicale-0.6.1.tar.gz)
    (30 KiB)
  - [Radicale-0.6.tar.gz](http://pypi.python.org/packages/source/R/Radicale/Radicale-0.6.tar.gz)
    (30 KiB)
  - [Radicale-0.5.tar.gz](http://pypi.python.org/packages/source/R/Radicale/Radicale-0.5.tar.gz)
    (24 KiB)
  - [Radicale-0.4.tar.gz](http://pypi.python.org/packages/source/R/Radicale/Radicale-0.4.tar.gz)
    (23 KiB)
  - [Radicale-0.3.tar.gz](http://pypi.python.org/packages/source/R/Radicale/Radicale-0.3.tar.gz)
    (22 KiB)
  - [Radicale-0.2.tar.gz](http://pypi.python.org/packages/source/R/Radicale/Radicale-0.2.tar.gz)
    (22 KiB)

### Linux Distribution Packages

Radicale has been packaged for:

  - [ArchLinux (AUR)](https://aur.archlinux.org/packages/radicale/) by
    Guillaume Bouchard
  - [Debian](http://packages.debian.org/radicale) by Jonas Smedegaard
  - [Gentoo (Sunrise
    Overlay)](http://bugs.gentoo.org/show_bug.cgi?id=322811) by René
    Neumann
  - [Fedora](https://admin.fedoraproject.org/pkgdb/package/radicale/) by
    Jorti
  - [Mandriva/Mageia](http://sophie.zarb.org/search/results?search=radicale)
    by Jani Välimaa
  - [OpenBSD](http://openports.se/productivity/radicale) by Sergey
    Bronnikov, Stuart Henderson and Ian Darwin
  - [openSUSE](http://software.opensuse.org/package/Radicale?search_term=radicale)
  - [PyPM](http://code.activestate.com/pypm/radicale/)
  - [Slackware](http://schoepfer.info/slackware.xhtml#packages-network)
    by Johannes Schöpfer
  - [Trisquel](http://packages.trisquel.info/search?searchon=names&keywords=radicale)
  - [Ubuntu](http://packages.ubuntu.com/radicale) by the MOTU and Jonas
    Smedegaard

Radicale is also [available on
Cloudron](https://cloudron.io/button.html?app=org.radicale.cloudronapp)
and has a Dockerfile.

If you are interested in creating packages for other Linux
distributions, read the ["Contribute" page](#contribute).

# News


## May 19, 2020 - Radicale 1.1.7

Radicale 1.1.7 is out\!

### 1.1.7 - Third Law of Nature

  - Fix error in `--export-storage`
  - Include documentation in source archive

## Jul 24, 2017 - Radicale 1.1.6

Radicale 1.1.6 is out\!

### 1.1.6 - Third Law of Nature

  - Improve logging for `--export-storage`

## Jul 24, 2017 - Radicale 1.1.5

Radicale 1.1.5 is out\!

### 1.1.5 - Third Law of Nature

  - Improve logging for `--export-storage`

## Jun 25, 2017 - Radicale 1.1.4

Radicale 1.1.4 is out\!

### 1.1.4 - Third Law of Nature

  - Use shutil.move for `--export-storage`

## May 27, 2017 - Radicale 1.1.3

Radicale 1.1.3 is out\!

### 1.1.3 - Third Law of Nature

  - Add a `--export-storage=FOLDER` command-line argument (by Unrud, see
    [#606](https://github.com/Kozea/Radicale/pull/606))

## April 19, 2017 - Radicale 1.1.2

Radicale 1.1.2 is out\!

### 1.1.2 - Third Law of Nature

  - Security fix: Add a random timer to avoid timing oracles and simple
    bruteforce attacks when using the htpasswd authentication method.
  - Various minor fixes.

## December 31, 2015 - Radicale 1.1

Radicale 1.1 is out\!

### 1.1 - Law of Nature

One feature in this release is **not backward compatible**:

  - Use the first matching section for rights (inspired from daald)

Now, the first section matching the path and current user in your custom
rights file is used. In the previous versions, the most permissive
rights of all the matching sections were applied. This new behaviour
gives a simple way to make specific rules at the top of the file
independant from the generic ones.

Many **improvements in this release are related to security**, you
should upgrade Radicale as soon as possible:

  - Improve the regex used for well-known URIs (by Unrud)
  - Prevent regex injection in rights management (by Unrud)
  - Prevent crafted HTTP request from calling arbitrary functions (by
    Unrud)
  - Improve URI sanitation and conversion to filesystem path (by Unrud)
  - Decouple the daemon from its parent environment (by Unrud)

Some bugs have been fixed and little enhancements have been added:

  - Assign new items to corret key (by Unrud)
  - Avoid race condition in PID file creation (by Unrud)
  - Improve the docker version (by cdpb)
  - Encode message and commiter for git commits
  - Test with Python 3.5

## September 14, 2015 - Radicale 1.0, what's next?

Radicale 1.0 is out\!

### 1.0 - Sunflower

  - Enhanced performances (by Mathieu Dupuy)
  - Add MD5-APR1 and BCRYPT for htpasswd-based authentication (by
    Jan-Philip Gehrcke)
  - Use PAM service (by Stephen Paul Weber)
  - Don't discard PROPPATCH on empty collections (Markus Unterwaditzer)
  - Write the path of the collection in the git message (Matthew Monaco)
  - Tests launched on Travis

As explained in a previous
[mail](http://librelist.com/browser//radicale/2015/8/21/radicale-1-0-is-coming-what-s-next/),
this version is called 1.0 because:

  - there are no big changes since 0.10 but some small changes are
    really useful,
  - simple tests are now automatically launched on Travis, and more can
    be added in the future (<https://travis-ci.org/Kozea/Radicale>).

This version will be maintained with only simple bug fixes on a separate
git branch called `1.0.x`.

Now that this milestone is reached, it's time to think about the future.
When Radicale has been created, it was just a proof-of-concept. The main
goal was to write a small, stupid and simple CalDAV server working with
Lightning, using no external libraries. That's how we created a piece of
code that's (quite) easy to understand, to use and to hack.

The first lines have been added to the SVN (\!) repository as I was
drinking beers at the very end of 2008. It's now packaged for a growing
number of Linux distributions.

And that was fun going from here to there thanks to you. So… **Thank
you, you're amazing**. I'm so glad I've spent endless hours fixing
stupid bugs, arguing about databases and meeting invitations, reading
incredibly interesting RFCs and debugging with the fabulous clients from
Apple. I mean: that really, really was really, really cool :).

During these years, a lot of things have changed and many users now rely
on Radicale in production. For example, I use it to manage medical
calendars, with thousands requests per day. Many people are happy to
install Radicale on their small home servers, but are also frustrated by
performance and unsupported specifications when they're trying to use it
seriously.

So, now is THE FUTURE\! I think that Radicale 2.0 should:

  - rely on a few external libraries for simple critical points (dealing
    with HTTP and iCal for example),
  - be thread-safe,
  - be small,
  - be documented in a different way (for example by splitting the
    client part from the server part, and by adding use cases),
  - let most of the "auth" modules outside in external modules,
  - have more and more tests,
  - have reliable and faster filesystem and database storage mechanisms,
  - get a new design :).

I'd also secretly love to drop the Python 2.x support.

These ideas are not all mine (except from the really, really, really
important "design" point :p), they have been proposed by many developers
and users. I've just tried to gather them and keep points that seem
important to me.

Other points have been discussed with many users and contibutors,
including:

  - support of other clients, including Windows and BlackBerry phones,
  - server-side meeting invitations,
  - different storage system as default (or even unique?).

I'm not a huge fan of these features, either because I can't do anything
about them, or because I think that they're Really Bad Ideas®™. But I'm
ready to talk about them, because, well, I may not be always right\!

Need to talk about this? You know how to [contact us](#contribute)\!

## January 12, 2015 - Radicale 0.10

Radicale 0.10 is out\!

### 0.10 - Lovely Endless Grass

  - Support well-known URLs (by Mathieu Dupuy)
  - Fix collection discovery (by Markus Unterwaditzer)
  - Reload logger config on SIGHUP (by Élie Bouttier)
  - Remove props files when deleting a collection (by Vincent Untz)
  - Support salted SHA1 passwords (by Marc Kleine-Budde)
  - Don't spam the logs about non-SSL IMAP connections to localhost (by
    Giel van Schijndel)

This version should bring some interesting discovery and
auto-configuration features, mostly with Apple clients.

Lots of love and kudos for the people who have spent hours to test
features and report issues, that was long but really useful (and some of
you have been really patient :p).

Issues are welcome, I'm sure that you'll find horrible, terrible, crazy
bugs faster than me. I'll release a version 0.10.1 if needed.

What's next? It's time to fix and improve the storage methods. A real
API for the storage modules is a good beginning, many pull requests are
already ready to be discussed and merged, and we will probably get some
good news about performance this time. Who said "databases, please"?

## July 12, 2013 - Radicale 0.8

Radicale 0.8 is out\!

### 0.8 - Rainbow

  - New authentication and rights management modules (by Matthias
    Jordan)
  - Experimental database storage
  - Command-line option for custom configuration file (by Mark Adams)
  - Root URL not at the root of a domain (by Clint Adams, Fabrice
    Bellet, Vincent Untz)
  - Improved support for iCal, CalDAVSync, CardDAVSync, CalDavZAP and
    CardDavMATE
  - Empty PROPFIND requests handled (by Christoph Polcin)
  - Colon allowed in passwords
  - Configurable realm message

This version brings some of the biggest changes since Radicale's
creation, including an experimental support of database storage, clean
authentication modules, and rights management finally designed for real
users.

So, dear user, be careful: **this version changes important things in
the configuration file, so check twice that everything is OK when you
update to 0.8, or you can have big problems**.

More and more clients are supported, as a lot of bug fixes and features
have been added for this purpose. And before you ask: yes, 2 web-based
clients, [CalDavZAP and
CardDavMATE](http://www.inf-it.com/open-source/clients/), are now
supported\!

Even if there has been a lot of time to test these new features, I am
pretty sure that some really annoying bugs have been left in this
version. We will probably release minor versions with bugfixes during
the next weeks, and it will not take one more year to reach 0.8.1.

The documentation has been updated, but some parts are missing and some
may be out of date. You can [report
bugs](https://github.com/Kozea/Radicale/issues) or even [write
documentation directly on
GitHub](https://github.com/Kozea/Radicale/blob/website/pages/user_documentation.rst)
if you find something strange (and you probably will).

If anything is not clear, or if the way rights work is a bit complicated
to understand, or if you are so happy because everything works so well,
you can [share your thoughts](#contribute)\!

It has been a real pleasure to work on this version, with brilliant
ideas and interesting bug reports from the community. I'd really like to
thank all the people reporting bugs, chatting on IRC, sending mails and
proposing pull requests: you are awesome.

## August 3, 2012 - Radicale 0.7.1

Radicale 0.7.1 is out\!

### 0.7.1 - Waterfalls

  - Many address books fixes
  - New IMAP ACL (by Daniel Aleksandersen)
  - PAM ACL fixed (by Daniel Aleksandersen)
  - Courier ACL fixed (by Benjamin Frank)
  - Always set display name to collections (by Oskari Timperi)
  - Various DELETE responses fixed

It's been a long time since the last version… As usual, many people have
contributed to this new version, that's a pleasure to get these pull
requests.

Most of the commits are bugfixes, especially about ACL backends and
address books. Many clients (including aCal and SyncEvolution) will be
much happier with this new version than with the previous one.

By the way, one main new feature has been added: a new IMAP ACL backend,
by Daniel. And about authentication, exciting features are coming soon,
stay tuned\!

Next time, as many mails have come from angry and desperate coders,
tests will be *finally* added to help them to add features and fix bugs.
And after that, who knows, it may be time to release Radicale 1.0…

## March 22, 2012 - Radicale 0.7

Radicale 0.7 is out, at least\!

### 0.7 - Eternal Sunshine

  - Repeating events
  - Collection deletion
  - Courier and PAM authentication methods
  - CardDAV support
  - Custom LDAP filters supported

**A lot** of people have reported bugs, proposed new features, added
useful code and tested many clients. Thank you Lynn, Ron, Bill, Patrick,
Hidde, Gerhard, Martin, Brendan, Vladimir, and everybody I've forgotten.

## January 5, 2012 - Radicale 0.6.4, News from Calypso

New year, new release. Radicale 0.6.4 has a really short changelog:

### 0.6.4 - Tulips

  - Fix the installation with Python 3.1

The bug was in fact caused by a [bug in
Python 3.1](http://bugs.python.org/issue9561), everything should be OK
now.

### Calypso

After a lot of changes in Radicale, Keith Packard has decided to launch
a fork called [Calypso](http://keithp.com/blogs/calypso/), with nice
features such as a Git storage mechanism and a CardDAV support.

There are lots of differences between the two projects, but the final
goal for Radicale is to provide these new features as soon as possible.
Thanks to the work of Keith and other people on GitHub, a basic CardDAV
support has been added in the [carddav
branch](https://github.com/Kozea/Radicale/tree/carddav) and already
works with Evolution. Korganizer also works with existing address books,
and CardDAV-Sync will be tested soon. If you want to test other clients,
please let us know\!

## November 3, 2011 - Radicale 0.6.3

Radicale version 0.6.3 has been released, with bugfixes that could be
interesting for you\!

### 0.6.3 - Red Roses

  - MOVE requests fixed
  - Faster REPORT answers
  - Executable script moved into the package

### What's New Since 0.6.2?

The MOVE requests were suffering a little bug that is fixed now. These
requests are only sent by Apple clients, Mac users will be happy.

The REPORT request were really, really slow (several minutes for large
calendars). This was caused by an awful algorithm parsing the entire
calendar for each event in the calendar. The calendar is now only parsed
three times, and the events are found in a Python list, turning minutes
into seconds\! Much better, but far from perfection…

Finally, the executable script parsing the command line options and
starting the HTTP servers has been moved from the `radicale.py` file
into the `radicale` package. Two executable are now present in the
archive: the good old `radicale.py`, and `bin/radicale`. The second one
is only used by `setup.py`, where the hack used to rename `radicale.py`
into `radicale` has therefore been removed. As a consequence, you can
now launch Radicale with the simple `python -m radicale` command,
without relying on an executable.

### Time for a Stable Release\!

The next release may be a stable release, symbolically called 1.0. Guess
what's missing? Tests, of course\!

A non-regression testing suite, based on the clients' requests, will
soon be added to Radicale. We're now thinking about a smart solution to
store the tests, to represent the expected answers and to launch the
requests. We've got crazy ideas, so be prepared: you'll definitely
*want* to write tests during the next weeks\!

Repeating events, PAM and Courier authentication methods have already
been added in master. You'll find them in the 1.0 release\!

### What's Next?

Being stable is one thing, being cool is another one. If you want some
cool new features, you may be interested in:

  - WebDAV and CardDAV support
  - Filters and rights management
  - Multiple storage backends, such as databases and git
  - Freebusy periods
  - Email alarms

Issues have been reported in the bug tracker, you can follow there the
latest news about these features. Your beloved text editor is waiting
for you\!

## September 27, 2011 - Radicale 0.6.2

0.6.2 is out with minor bugfixes.

### 0.6.2 - Seeds

  - iPhone and iPad support fixed
  - Backslashes replaced by slashes in PROPFIND answers on Windows
  - PyPI archive set as default download URL

## August 28, 2011 - Radicale 0.6.1, Changes, Future

As previously imagined, a new 0.6.1 version has been released, mainly
fixing obvious bugs.

### 0.6.1 - Growing Up

  - Example files included in the tarball
  - htpasswd support fixed
  - Redirection loop bug fixed
  - Testing message on GET requests

The changelog is really small, so there should be no real new problems
since 0.6. The example files for logging, FastCGI and WSGI are now
included in the tarball, for the pleasure of our dear packagers\!

A new branch has been created for various future bug fixes. You can
expect to get more 0.6.x versions, making this branch a kind of "stable"
branch with no big changes.

### GitHub, Mailing List, New Website

A lot of small changes occurred during the last weeks.

If you're interested in code and new features, please note that we moved
the project from Gitorious to `GitHub`. Being hosted by Gitorious was a
nice experience, but the service was not that good and we were missing
some useful features such as git hooks. Moreover, GitHub is really
popular, we're sure that we'll meet a lot of kind users and coders
there.

We've also created a `mailing-list on Librelist` to keep a public trace
of the mails we're receiving. It a bit empty now, but we're sure that
you'll soon write us some kind words. For example, you can tell us what
you think of our new website\!

### Future Features

In the next weeks, new exciting features are coming in the master
branch\! Some of them are almost ready:

  - Henry-Nicolas has added the support for the PAM and
    Courier-Authdaemon authentication mechanisms.
  - An anonymous called Keith Packard has prepared some small changes,
    such as one file per event, cache and git versioning. Yes. Really.

As you can find in the [Radicale
Roadmap](http://redmine.kozea.fr/versions/), tests, rights and filters
are expected for 0.7.

## August 1, 2011 - Radicale 0.6 Released

Time for a new release with **a lot** of new exciting features\!

### 0.6 - Sapling

  - WSGI support
  - IPv6 support
  - Smart, verbose and configurable logs
  - Apple iCal 4 and iPhone support (by Łukasz Langa)
  - CalDAV-Sync support (by Marten Gajda)
  - aCal support
  - KDE KOrganizer support
  - LDAP auth backend (by Corentin Le Bail)
  - Public and private calendars (by René Neumann)
  - PID file
  - MOVE requests management
  - Journal entries support
  - Drop Python 2.5 support

Well, it's been a little longer than expected, but for good reasons: a
lot of features have been added, and a lot of clients are known to work
with Radicale, thanks to kind contributors. That's definitely good
news\! But…

Testing all the clients is really painful, moreover for the ones from
Apple (I have no Mac nor iPhone of my own). We should seriously think of
automated tests, even if it's really hard to maintain, and maybe not
that useful. If you're interested in tests, you can look at [the
wonderful regression suite of
DAViCal](http://repo.or.cz/w/davical.git/tree/HEAD:/testing/tests/regression-suite).

The new features, for example the WSGI support, are also poorly
documented. If you have some Apache or lighttpd configuration working
with Radicale, you can make the world a little bit better by writing a
paragraph or two in the [Radicale
documentation](https://gitorious.org/radicale/website). It's simple
plain text, don't be afraid\!

Because of all these changes, Radicale 0.6 may be a little bit buggy; a
0.6.1 will probably be released soon, fixing small problems with clients
and features. Get ready to report bugs, I'm sure that you can find one
(and fix it)\!

## July 2, 2011 - Feature Freeze for 0.6

According to the
[roadmap](http://redmine.kozea.fr/projects/radicale/roadmap), a lot of
features have been added since Radicale 0.5, much more than expected.
It's now time to test Radicale with your favourite client and to report
bugs before we release the next stable version\!

Last week, the iCal and iPhone support written by Łukasz has been fixed
in order to restore the broken Lightning support. After two afternoons
of tests with Rémi, we managed to access the same calendar with
Lightning, iCal, iPhone and Evolution, and finally discovered that
CalDAV could also be a perfect instant messaging protocol between a Mac,
a PC and a phone.

After that, we've had the nice surprise to see events displayed without
a problem (but after some strange steps of configuration) by aCal on
Salem's Android phone.

It was Friday, fun fun fun fun.

So, that's it: Radicale supports Lightning, Evolution, Kontact, aCal for
Android, iPhone and iCal. Of course, before releasing a new tarball:

  - [documentation](#documentation/user-documentation/simple-usage/starting-the-client)
    is needed for the new clients that are not documented yet (Kontact,
    aCal and iPhone);
  - tests are welcome, particularly for the Apple clients that I can't
    test anymore;
  - no more features will be added, they'll wait in separate branches
    for the 0.7 development.

Please [report bugs](http://redmine.kozea.fr/projects/radicale/issues)
if anything goes wrong during your tests, or just let us know [by Jabber
or by mail](#contribute) if everything is OK.

## May 1, 2011 - Ready for WSGI

Here it is\! Radicale is now ready to be launched behind your favourite
HTTP server (Apache, Lighttpd, Nginx or Tomcat for example). That's
really good news, because:

  - Real HTTP servers are much more efficient and reliable than the
    default Python server used in Radicale;
  - All the authentication backends available for your server will be
    available for Radicale;
  - Thanks to [flup](http://trac.saddi.com/flup), Radicale can be
    interfaced with all the servers supporting CGI, AJP, FastCGI or
    SCGI;
  - Radicale works very well without any additional server, without any
    dependencies, without configuration, just as it was working before;
  - This one more feature removes useless code, less is definitely more.

The WSGI support has only be tested as a stand-alone executable and
behind Lighttpd, you should definitely try if it works with you
favourite server too\!

No more features will be added before (quite) a long time, because a lot
of documentation and test is waiting for us. If you want to write
tutorials for some CalDAV clients support (iCal, Android, iPhone), HTTP
servers support or logging management, feel free to fork the
[documentation git repository](https://gitorious.org/radicale/website)
and ask for a merge. It's plain text, I'm sure you can do it\!

## April 30, 2011 - Apple iCal Support

After a long, long work, the iCal support has finally been added to
Radicale\! Well, this support is only for iCal 4 and is highly
experimental, but you can test it right now with the git master branch.
Bug reports are welcome\!

Dear MacOS users, you can thank all the gentlemen who sended a lot of
debugging iformation. Special thanks to Andrew from DAViCal, who helped
us a lot with his tips and his tests, and Rémi Hainaud who lent his
laptop for the final tests.

The default server address is `localhost:5232/user/`, where calendars
can be added. Multiple calendars and owner-less calendars are not tested
yet, but they should work quite well. More documentation will be added
during the next days. It will then be time to release the Radicale 0.6
version, and work on the WSGI support.

## April 25, 2011 - Two Features and One New Roadmap

Two features have just reached the master branch, and the roadmap has
been refreshed.

### LDAP Authentication

Thanks to Corentin, the LDAP authentication is now included in Radicale.
The support is experimental and may suffer unstable connexions and
security problems. If you are interested in this feature (a lot of
people seem to be), you can try it and give some feedback.

No SSL support is included yet, but this may be quite easy to add. By
the way, serious authentication methods will rely on a "real" HTTP
server, as soon as Radicale supports WSGI.

### Journal Entries

Mehmet asked for the journal entries (aka. notes or memos) support,
that's done\! This also was an occasion to clean some code in the iCal
parser, and to add a much better management of multi-lines entries.
People experiencing crazy `X-RADICALE-NAME` entries can now clean their
files, Radicale won't pollute them again.

### New Roadmap

Except from htpasswd and LDAP, most of the authentication backends
(database, SASL, PAM, user groups) are not really easy to include in
Radicale. The easiest solution to solve this problem is to give Radicale
a CGI support, to put it behind a solid server such as Apache. Of
course, CGI is not enough: a WSGI support is quite better, with the
FastCGI, AJP and SCGI backends offered by
[flup](http://trac.saddi.com/flup/). Quite exciting, isn't it?

That's why it was important to add new versions on the roadmap. The 0.6
version is now waiting for the Apple iCal support, and of course for
some tests to kill the last remaining bugs. The only 0.7 feature will be
WSGI, allowing many new authentication methods and a real multithread
support.

After that, 0.8 may add CalDAV rights and filters, while 1.0 will draw
thousands of rainbows and pink unicorns (WebDAV sync, CardDAV,
Freebusy). A lot of funky work is waiting for you, hackers\!

### Bugs

Many bugs have also been fixed, most of them due to the owner-less
calendars support. Radicale 0.6 may be out in a few weeks, you should
spend some time testing the master branch and filling the bug tracker.

## April 10, 2011 - New Features

Radicale 0.5 was released only 8 days ago, but 3 new features have
already been added to the master branch:

  - IPv6 support, with multiple addresses/ports support
  - Logs and debug mode
  - Owner-less calendars

Most of the code has been written by Necoro and Corentin, and that was
not easy at all: Radicale is now multithreaded\! For sure, you can find
many bugs and report them on the [bug
tracker](http://redmine.kozea.fr/projects/radicale/issues). And if
you're fond of logging, you can even add a default configuration file
and more debug messages in the source.

## April 2, 2011 - Radicale 0.5 Released

Radicale 0.5 is out\! Here is what's new:

### 0.5 - Historical Artifacts

  - Calendar depth
  - iPhone support
  - MacOS and Windows support
  - HEAD requests management
  - htpasswd user from calendar path

iPhone support, but no iCal support for 0.5, despite our hard work,
sorry\! After 1 month with no more activity on the dedicated bug, it was
time to forget it and hack on new awesome features. Thanks for your
help, dear Apple users, I keep the hope that one day, Radicale will work
with you\!

So, what's next? As promised, some cool git branches will soon be
merged, with LDAP support, logging, IPv6 and anonymous calendars. Sounds
pretty cool, heh? Talking about new features, more and more people are
asking for a CardDAV support in Radicale. [A git
branch](https://www.gitorious.org/~deepdiver/radicale/deepdivers-radicale)
and [a feature request](http://redmine.kozea.fr/issues/247) are open,
feel free to hack and discuss.

## February 3, 2011 - Jabber Room and iPhone Support

After a lot of help and testing work from Andrew, Björn, Anders, Dorian
and Pete (and other ones we could have forgotten), a simple iPhone
support has been added in the git repository. If you are interested, you
can test this feature *right now* by [downloading the latest git
version](#download//git-repository) (a tarball is even
available too if you don't want or know how to use git).

No documentation has been written yet, but using the right URL in the
configuration should be enough to synchronize your calendars. If you
have any problems, you can ask by joining our new Jabber room:
<radicale@room.jabber.kozea.fr>.

Radicale 0.5 will be released as soon as the iCal support is ready. If
you have an Apple computer, Python skills and some time to spend, we'd
be glad to help you debugging Radicale.

## October 21, 2010 - News from Radicale

During the last weeks, Radicale has not been idle, even if no news have
been posted since August. Thanks to Pete, Pierre-Philipp and Andrew,
we're trying to add a better support on MacOS, Windows and mobile
devices like iPhone and Android-based phones.

All the tests on Windows have been successful: launching Radicale and
using Lightning as client works without any problems. On Android too,
some testers have reported clients working with Radicale. These were the
good news.

The bad news come from Apple: both iPhone and MacOS default clients are
not working yet, despite the latest enhancements given to the PROPFIND
requests. The problems are quite hard to debug due to our lack of Apple
hardware, but Pete is helping us in this difficult quest\! Radicale 0.5
will be out as soon as these two clients are working.

Some cool stuff is coming next, with calendar collections and groups,
and a simple web-based CalDAV client in early development. Stay tuned\!

## August 8, 2010 - Radicale 0.4 Released

Radicale 0.4 is out\! Here is what's new:

### 0.4 - Hot Days Back

  - Personal calendars
  - HEAD requests
  - Last-Modified HTTP header
  - `no-ssl` and `foreground` options
  - Default configuration file

This release has mainly been released to help our dear packagers to
include a default configuration file and to write init scripts. Big
thanks to Necoro for his work on the new Gentoo ebuild\!

## July 4, 2010 - Three Features Added Last Week

Some features have been added in the git repository during the last
weeks, thanks to Jerome and Mariusz\!

  - Personal Calendars  
    Calendars accessed through the htpasswd ACL module can now be
    personal. Thanks to the `personal` option, a user called `bob` can
    access calendars at `/bob/*` but not to the `/alice/*` ones.

  - HEAD Requests  
    Radicale can now answer HEAD requests. HTTP headers can be retrieved
    thanks to this request, without getting contents given by the GET
    requests.

  - Last-Modified HTTP header  
    The Last-Modified header gives the last time when the calendar has
    been modified. This is used by some clients to cache the calendars
    and not retrieving them if they have not been modified.

## June 14, 2010 - Radicale 0.3 Released

Radicale 0.3 is out\! Here is what’s new:

### 0.3 - Dancing Flowers

  - Evolution support
  - Version management

The website changed a little bit too, with some small HTML5 and CSS3
features such as articles, sections, transitions, opacity, box shadows
and rounded corners. If you’re reading this website with Internet
Explorer, you should consider using a standard-compliant browser\!

Radicale is now included in Squeeze, the testing branch of Debian. A
[Radicale ebuild for
Gentoo](http://bugs.gentoo.org/show_bug.cgi?id=322811) has been proposed
too. If you want to package Radicale for another distribution, you’re
welcome\!

Next step is 0.5, with calendar collections, and Windows and MacOS
support.

## May 31, 2010 - May News

### News from contributors

Jonas Smedegaard packaged Radicale for Debian last week. Two packages,
called `radicale` for the daemon and `python-radicale` for the module,
have been added to Sid, the unstable branch of Debian. Thank you,
Jonas\!

Sven Guckes corrected some of the strange-English-sentences present on
this website. Thank you, Sven\!

### News from software

A simple `VERSION` has been added in the library: you can now play with
`radicale.VERSION` and `$radicale --version`.

After playing with the version (should not be too long), you may notice
that the next version is called 0.3, and not 0.5 as previously decided.
The 0.3 main goal is to offer the support for Evolution as soon as
possible, without waiting for the 0.5. After more than a month of test,
we corrected all the bugs we found and everything seems to be fine; we
can imagine that a brand new tarball will be released during the first
days of June.

## April 19, 2010 - Evolution Supported

Radicale now supports another CalDAV client: [Evolution, the default
mail, addressbook and calendaring client for
Gnome](http://projects.gnome.org/evolution/). This feature was quite
easy to add, as it required less than 20 new lines of code in the
requests handler.

If you are interested, just clone the [git
repository](http://www.gitorious.org/radicale/radicale).

## April 13, 2010 - Radicale 0.2 Released

Radicale 0.2 is out\! Here is what’s new:

### 0.2 - Snowflakes

  - Sunbird pre-1.0 support
  - SSL connection
  - Htpasswd authentication
  - Daemon mode
  - User configuration
  - Twisted dependency removed
  - Python 3 support
  - Real URLs for PUT and DELETE
  - Concurrent modification reported to users
  - Many bugs fixed by Roger Wenham

First of all, we would like to thank Roger Wenham for his bugfixes and
his supercool words.

You may have noticed that Sunbird 1.0 has not been released, but
according to the Mozilla developers, 1.0pre is something like a final
version.

You may have noticed too that Radicale can be [downloaded from
PyPI](http://pypi.python.org/pypi/Radicale/0.2). Of course, it is also
available on the [download page](#download).

## January 21, 2010 - HTTPS and Authentication

HTTPS connections and authentication have been added to Radicale this
week. Command-line options and personal configuration files are also
ready for test. According to the TODO file included in the package, the
next version will finally be 0.2, when sunbird 1.0 is out. Go, Mozilla
hackers, go\!

  - HTTPS connection  
    HTTPS connections are now available using the standard TLS
    mechanisms. Give Radicale a private key and a certificate, and your
    data are now safe.

  - Authentication  
    A simple authentication architecture is now available, allowing
    different methods thanks to different modules. The first two modules
    are `fake` (no authentication) and `htpasswd` (authentication with
    an `htpasswd` file created by the Apache tool). More methods such as
    LDAP are coming soon\!

## January 15, 2010 - Ready for Python 3

Dropping Twisted dependency was the first step leading to another big
feature: Radicale now works with Python 3\! The code was given a small
cleanup, with some simplifications mainly about encoding. Before the
0.1.1 release, feel free to test the git repository, all Python versions
from 2.5 should be OK.

## January 11, 2010 - Twisted no Longer Required

Good news\! Radicale 0.1.1 will support Sunbird 1.0, but it has another
great feature: it has no external dependency\! Twisted is no longer
required for the git version, removing about 50 lines of code.

## December 31, 2009 - Lightning and Sunbird 1.0b2pre Support

Lightning/Sunbird 1.0b2pre is out, adding minor changes in CalDAV
support. A [new
commit](http://www.gitorious.org/radicale/radicale/commit/330283e) makes
Radicale work with versions 0.9, 1.0b1 et 1.0b2. Moreover, etags are now
quoted according to the
[RFC 2616](http://www.faqs.org/rfcs/rfc2616.html "RFC 2616").

## December 9, 2009 - Thunderbird 3 released

[Thunderbird 3 is
out](http://www.mozillamessaging.com/thunderbird/3.0/releasenotes/), and
Lightning/Sunbird 1.0 should be released in a few days. The [last commit
in git](http://gitorious.org/radicale/radicale/commit/6545bc8) should
make Radicale work with versions 0.9 and 1.0b1pre. Radicale 0.1.1 will
soon be released adding support for version 1.0.

## September 1, 2009 - Radicale 0.1 Released

First Radicale release\! Here is the changelog:

### 0.1 - Crazy Vegetables

  - First release
  - Lightning/Sunbird 0.9 compatibility
  - Easy installer

You can download this version on the [download page](#download).

## July 28, 2009 - Radicale on Gitorious

Radicale code has been released on Gitorious\! Take a look at the
[Radicale main page on Gitorious](http://www.gitorious.org/radicale) to
view and download source code.

## July 27, 2009 - Radicale Ready to Launch

The Radicale Project is launched. The code has been cleaned up and will
be available soon…

# Footnotes

### 1

See [Python Versions and OS
Support](#documentation/user-documentation/python-versions-and-os-support) for further information.

### 2

[Python download page](http://python.org/download/).

### 3

I repeat: [we are
lazy](#documentation/technical-choices/global-technical-choices/development-choices/lazy).

### 4

Try to read
[RFC 4791](http://www.faqs.org/rfcs/rfc4791.html "RFC 4791"). Then
try to understand it. Then try to implement it. Then try to read it
again.

### 5

Radicale is [oriented to calendar user
agents](#documentation/technical-choices/global-technical-choices/development-choices/oriented-to-calendar-and-contact-user-agents).

### 6

[CalDAV
implementations](http://en.wikipedia.org/wiki/CalDAV#Implementations),
by Wikipedia.

### 7

[Davical](http://www.davical.org/), a standards-compliant calendar
server.

### 8

[Cosmo](http://chandlerproject.org/Projects/CosmoHome), the web
contents and calendars sharing server build to support the Chandler
Project.

### 9

[Darwin Calendar Server](http://trac.calendarserver.org/), a
standards-compliant calendar server mainly developed by Apple.

### 10

Who says "Ruby is even less verbose\!" should read the
[PEP 20](http://www.python.org/dev/peps/pep-0020/ "PEP 20").
